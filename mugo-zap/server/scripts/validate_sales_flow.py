from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import sales_brain


def assert_equal(name: str, got, expected):
    if got != expected:
        raise AssertionError(f"{name}: expected {expected!r}, got {got!r}")


def assert_true(name: str, value):
    if not value:
        raise AssertionError(f"{name}: expected truthy value, got {value!r}")


def state_with_choice(choice_id: str) -> dict:
    return sales_brain.merge_state(sales_brain.default_lead_state(), sales_brain.service_choice_update(choice_id))


def pipeline_step(
    state: dict,
    *,
    message: str = "",
    button_id: str = "",
    button_title: str = "",
    list_id: str = "",
    list_title: str = "",
    list_description: str = "",
    forced_reply: str = "",
    ai_result: dict | None = None,
) -> dict:
    state_before = sales_brain.flatten_state(state)
    text = message or button_title or list_title or list_description or button_id or list_id
    choice = sales_brain.normalize_inbound_choice(
        text=text,
        button_id=button_id,
        button_title=button_title,
        list_id=list_id,
        list_title=list_title,
        list_description=list_description,
        current_state=state_before,
    )
    signals = {}
    state_after = state_before
    if choice.get("is_menu_choice") and choice.get("choice_id"):
        state_after = sales_brain.merge_state(state_after, sales_brain.service_choice_update(choice["choice_id"]))
    else:
        signals = sales_brain.extract_signal_from_message(text, state_after)
        state_after = sales_brain.merge_state(state_after, signals)

    next_q = sales_brain.get_next_question(state_after)
    used_openai = bool(ai_result)
    if ai_result:
        ai_fields = ai_result.get("lead_fields") if isinstance(ai_result.get("lead_fields"), dict) else {}
        state_after = sales_brain.merge_state(state_after, ai_fields)
        state_after = sales_brain.merge_state(state_after, signals)
        if (
            ai_result.get("handoff")
            or ai_result.get("next_action") == "handoff"
            or ai_result.get("briefing_ready")
            or ai_result.get("lead_temperature") == "hot"
        ):
            state_after = sales_brain.merge_state(
                state_after,
                {
                    "handoff": True,
                    "handoff_reason": ai_result.get("handoff_reason") or "ai_handoff",
                    "lead_temperature": "hot",
                    "meeting_suggested": True,
                    "briefing_ready": True,
                    "next_action": "handoff",
                },
            )
        next_q = sales_brain.get_next_question(state_after)

    if sales_brain.should_offer_meeting(state_after):
        state_after = sales_brain.merge_state(
            state_after,
            {
                "handoff": True,
                "handoff_reason": state_after.get("handoff_reason") or "lead_qualificado_ou_urgente",
                "lead_temperature": "hot" if state_after.get("urgency") == "alta" else "warm",
                "meeting_suggested": True,
                "briefing_ready": True,
                "next_action": "handoff",
            },
        )
        next_q = sales_brain.get_next_question(state_after)

    reply = forced_reply or (ai_result or {}).get("reply") or sales_brain.build_contextual_reply(state_before, state_after, signals, next_q)
    validation = sales_brain.validate_final_reply(reply, state_after)
    if validation.get("blocked"):
        replacement = {
            "category": validation.get("category") or next_q.get("category"),
            "question": validation.get("question") or validation.get("reply") or next_q.get("question"),
            "next_action": validation.get("next_action") or next_q.get("next_action"),
        }
        reply = sales_brain.build_contextual_reply(state_before, state_after, signals, replacement) or validation["reply"]
        next_q = {
            "category": validation.get("category") or next_q.get("category"),
            "question": validation.get("question") or next_q.get("question") or reply,
            "next_action": validation.get("next_action") or next_q.get("next_action"),
        }

    if (
        state_after.get("handoff")
        or state_after.get("briefing_ready")
        or next_q.get("next_action") == "handoff"
        or (ai_result or {}).get("next_action") == "handoff"
        or (ai_result or {}).get("briefing_ready")
    ):
        from app import build_handoff_lead_reply

        reply = build_handoff_lead_reply(state_after)
        state_after = sales_brain.merge_state(
            state_after,
            {
                "handoff": True,
                "lead_temperature": "hot",
                "meeting_suggested": True,
                "briefing_ready": True,
                "next_action": "handoff",
            },
        )
        next_q = {"category": "handoff", "question": reply, "next_action": "handoff"}

    state_after = sales_brain.merge_state(
        state_after,
        {
            "last_question_asked": reply,
            "last_question_category": next_q["category"],
            "next_best_question": reply,
            "next_action": next_q["next_action"],
        },
    )
    return {
        "reply": reply,
        "normalized_choice": choice,
        "extracted_signals": signals,
        "state_before": state_before,
        "state_after": sales_brain.flatten_state(state_after),
        "next_question": next_q,
        "blocked_reason": validation.get("reason") or "",
        "used_openai": used_openai,
    }


def persisted_pipeline_step(store: dict, wa_id: str, **kwargs) -> dict:
    state = store.get(wa_id) or sales_brain.default_lead_state()
    result = pipeline_step(state, **kwargs)
    store[wa_id] = result["state_after"]
    return result


def dedupe_patch_state(existing_state: dict, message_id: str) -> dict:
    return sales_brain.merge_state(
        existing_state,
        {
            "last_in_msg_id": message_id,
            "last_in_at": "2026-04-29T19:42:39+00:00",
        },
    )


def apply_message(state: dict, message: str) -> dict:
    updates = sales_brain.extract_signal_from_message(message, state)
    state = sales_brain.merge_state(state, updates)
    next_q = sales_brain.get_next_question(state)
    return sales_brain.merge_state(
        state,
        {
            "last_question_asked": next_q["question"],
            "last_question_category": next_q["category"],
            "next_best_question": next_q["question"],
            "next_action": next_q["next_action"],
        },
    )


def run_test(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        raise


def test_menu_site():
    choice = sales_brain.normalize_inbound_choice(
        list_title="Site ou landing",
        list_description="Criar ou melhorar páginas",
    )
    assert_equal("choice_id", choice["choice_id"], "service_site")
    assert_equal("service_interest", choice["service_interest"], "site")
    assert_true("is_menu_choice", choice["is_menu_choice"])


def test_site_melhorar():
    state = state_with_choice("service_site")
    choice = sales_brain.normalize_inbound_choice(text="melhorar", current_state=state)
    assert_equal("contextual text is not menu", choice["is_menu_choice"], False)
    state = apply_message(state, "melhorar")
    flat = sales_brain.flatten_state(state)
    assert_equal("site_scope", flat["site_scope"], "melhorar existente")
    assert_equal("next category", sales_brain.get_next_question(flat)["category"], "main_goal")
    assert_equal("next question", sales_brain.get_next_question(flat)["question"], "O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?")


def test_site_do_zero():
    state = state_with_choice("service_site")
    state = apply_message(state, "criar do zero")
    assert_equal("site_scope", sales_brain.flatten_state(state)["site_scope"], "criar do zero")


def test_site_melhorar_frase():
    state = state_with_choice("service_site")
    state = apply_message(state, "melhorar uma página que já existe")
    assert_equal("site_scope", sales_brain.flatten_state(state)["site_scope"], "melhorar existente")


def test_text_site_without_state_is_menu():
    choice = sales_brain.normalize_inbound_choice(text="site", current_state={})
    assert_equal("choice_id", choice["choice_id"], "service_site")
    assert_equal("is_menu_choice", choice["is_menu_choice"], True)


def test_text_site_with_state_is_not_menu():
    state = state_with_choice("service_site")
    choice = sales_brain.normalize_inbound_choice(text="site", current_state=state)
    assert_equal("is_menu_choice", choice["is_menu_choice"], False)


def test_automation_choice():
    state = state_with_choice("service_automation")
    flat = sales_brain.flatten_state(state)
    assert_equal("service_interest", flat["service_interest"], "automacao_whatsapp")
    assert_equal("next category", sales_brain.get_next_question(flat)["category"], "lead_source")


def test_all_service_buttons():
    cases = {
        "service_site": ("site", "site_scope"),
        "service_automation": ("automacao_whatsapp", "lead_source"),
        "service_ai": ("inteligencia_artificial", "main_goal"),
        "service_traffic": ("trafego_pago", "current_status"),
        "service_branding": ("branding", "main_goal"),
        "service_human": ("humano", "handoff"),
    }
    for choice_id, (service, category) in cases.items():
        step = pipeline_step(sales_brain.default_lead_state(), list_id=choice_id)
        assert_equal(f"{choice_id} service", step["state_after"]["service_interest"], service)
        assert_equal(f"{choice_id} category", step["next_question"]["category"], category)
        if choice_id == "service_human":
            assert_equal("human handoff", step["state_after"]["handoff"], True)
            assert_true("human link", "https://wa.me/5511973510549?text=" in step["reply"])
        else:
            assert_equal(f"{choice_id} not handoff", bool(step["state_after"]["handoff"]), False)


def test_pipeline_automation_contextual_answers():
    step1 = pipeline_step(
        sales_brain.default_lead_state(),
        list_title="Automatizar WhatsApp",
        list_description="Atendimento, leads e CRM",
    )
    state = step1["state_after"]
    assert_equal("service_interest", state["service_interest"], "automacao_whatsapp")
    assert_equal("first category", step1["next_question"]["category"], "lead_source")

    step2 = pipeline_step(state, message="WhatsApp")
    state = step2["state_after"]
    assert_equal("whatsapp is not menu", step2["normalized_choice"]["is_menu_choice"], False)
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_equal("next category", step2["next_question"]["category"], "current_tools")

    step3 = pipeline_step(state, message="manualmente")
    state = step3["state_after"]
    assert_equal("current_tools", state["current_tools"], "manual")
    assert_equal("next category", step3["next_question"]["category"], "urgency")


def test_real_meta_list_reply_automation_payload():
    meta_payload = {
        "type": "list_reply",
        "list_reply": {
            "id": "service_automation",
            "title": "Automatizar WhatsApp",
            "description": "Atendimento, leads e CRM",
        },
    }
    list_reply = meta_payload["list_reply"]
    step1 = pipeline_step(
        sales_brain.default_lead_state(),
        list_id=list_reply["id"],
        list_title=list_reply["title"],
        list_description=list_reply["description"],
    )
    state = step1["state_after"]
    assert_equal("choice_id", step1["normalized_choice"]["choice_id"], "service_automation")
    assert_equal("service_interest", state["service_interest"], "automacao_whatsapp")
    assert_equal("reply", step1["reply"], "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?")

    step2 = pipeline_step(state, message="WhatsApp")
    state = step2["state_after"]
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_true("reply asks tools", "Hoje vocês atendem tudo manualmente ou já usam alguma ferramenta/CRM?" in step2["reply"])
    assert_true("did not repeat source", "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?" not in step2["reply"])


def test_ai_led_after_menu_choice():
    state = pipeline_step(
        sales_brain.default_lead_state(),
        list_id="service_automation",
        list_title="Automatizar WhatsApp",
        list_description="Atendimento, leads e CRM",
    )["state_after"]
    step = pipeline_step(
        state,
        message="quero vender mais pelo WhatsApp",
        ai_result={
            "reply": "Boa, então o foco é transformar o WhatsApp em um canal mais forte de vendas. Hoje vocês atendem tudo manualmente ou já usam algum CRM?",
            "intent": "automacao_whatsapp",
            "lead_temperature": "warm",
            "next_action": "ask_question",
            "handoff": False,
            "briefing_ready": False,
            "lead_fields": {
                "main_goal": "vendas/leads",
                "desired_result": "vender mais pelo WhatsApp",
                "service_interest": "automacao_whatsapp",
                "last_question_category": "current_tools",
            },
        },
    )
    assert_equal("used_openai", step["used_openai"], True)
    assert_equal("service kept", step["state_after"]["service_interest"], "automacao_whatsapp")
    assert_equal("main_goal", step["state_after"]["main_goal"], "vendas/leads")
    assert_true("ai phrasing kept", step["reply"].startswith("Boa, então o foco"))


def test_ai_repeat_is_blocked():
    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(
        state,
        {
            "lead_source": "WhatsApp",
            "last_question_asked": "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?",
            "last_question_category": "lead_source",
        },
    )
    step = pipeline_step(
        state,
        message="whatsapp",
        ai_result={
            "reply": "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?",
            "intent": "automacao_whatsapp",
            "next_action": "ask_question",
            "lead_fields": {"lead_source": "WhatsApp"},
        },
    )
    assert_equal("used_openai", step["used_openai"], True)
    assert_true("blocked repeat", step["blocked_reason"] in {"duplicate_last_question", "known_lead_source"})
    assert_true("replacement asks tools", "ferramenta/CRM" in step["reply"] or "CRM" in step["reply"])


def test_urgency_triggers_julia_handoff():
    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(
        state,
        {
            "main_goal": "vendas/leads",
            "lead_source": "WhatsApp",
            "current_tools": "manual",
            "last_question_category": "urgency",
        },
    )
    step = pipeline_step(
        state,
        message="essa semana",
        ai_result={
            "reply": "Perfeito, vou encaminhar seu contexto para a Julia e ela continua com você por aqui.",
            "intent": "automacao_whatsapp",
            "lead_temperature": "hot",
            "next_action": "handoff",
            "handoff": True,
            "briefing_ready": True,
            "lead_fields": {"urgency": "alta"},
        },
    )
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_equal("next_action", step["state_after"]["next_action"], "handoff")
    assert_equal("briefing_ready", step["state_after"]["briefing_ready"], True)


def test_julia_number_normalization():
    raw = "11973510549"
    normalized = "55" + re.sub(r"\D+", "", raw)
    assert_equal("julia whatsapp", normalized, "5511973510549")


def test_operation_number_normalization():
    from app import _normalize_brazil_whatsapp_number

    assert_equal("operation raw to wa", _normalize_brazil_whatsapp_number("11972769605"), "5511972769605")
    assert_equal("operation already normalized", _normalize_brazil_whatsapp_number("5511972769605"), "5511972769605")


def test_operation_briefing_numbers_include_both():
    from app import OPERATION_BRIEFING_NUMBERS

    assert_equal("operation briefing numbers", OPERATION_BRIEFING_NUMBERS, ["5511972769605", "5511986531008"])


def test_automation_leads():
    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(state, {"last_question_category": "lead_source"})
    state = apply_message(state, "instagram e whatsapp")
    assert_equal("lead_source", sales_brain.flatten_state(state)["lead_source"], "Instagram e WhatsApp")


def test_manual():
    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(state, {"last_question_category": "current_tools"})
    state = apply_message(state, "manualmente")
    flat = sales_brain.flatten_state(state)
    assert_equal("current_tools", flat["current_tools"], "manual")
    assert_equal("current_problem", flat["current_problem"], "processo manual")


def test_ai_context():
    state = state_with_choice("service_ai")
    state = sales_brain.merge_state(state, {"last_question_category": "main_goal"})
    state = apply_message(state, "atendimento e redes sociais")
    flat = sales_brain.flatten_state(state)
    assert_equal("service_interest", flat["service_interest"], "inteligencia_artificial")
    assert_equal("current_problem", flat["current_problem"], "atendimento e redes sociais")


def test_pipeline_ai_full_flow():
    state = pipeline_step(
        sales_brain.default_lead_state(),
        list_title="IA no negócio",
        list_description="Agentes, processos e escala",
    )["state_after"]
    assert_equal("service_interest", state["service_interest"], "inteligencia_artificial")

    step2 = pipeline_step(state, message="atendimento")
    state = step2["state_after"]
    assert_equal("main_goal", state["main_goal"], "atendimento")
    assert_equal("current_problem", state["current_problem"], "atendimento")
    assert_equal("next category", step2["next_question"]["category"], "lead_source")
    assert_true("microconfirmation atendimento", step2["reply"].startswith("Certo. Então faz sentido pensar em IA"))

    step3 = pipeline_step(state, message="whatsapp")
    state = step3["state_after"]
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_equal("next category", step3["next_question"]["category"], "current_tools")


def test_ai_three_channels_short_answer():
    state = state_with_choice("service_ai")
    state = sales_brain.merge_state(
        state,
        {
            "main_goal": "atendimento",
            "current_problem": "atendimento",
            "last_question_asked": "Hoje esses contatos chegam mais pelo WhatsApp, Instagram ou site?",
            "last_question_category": "lead_source",
        },
    )
    step = pipeline_step(state, message="pelos 3 canais")
    assert_equal("lead_source", step["state_after"]["lead_source"], "WhatsApp, Instagram e site")
    assert_equal("next category", step["next_question"]["category"], "current_tools")
    assert_true("does not repeat", "Hoje esses contatos chegam mais pelo WhatsApp, Instagram ou site?" not in step["reply"])


def test_branding_os_dois_short_answer():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="Os dois")
    assert_equal("main_goal", step["state_after"]["main_goal"], "posicionamento e conteúdo/redes sociais")
    assert_equal("next category", step["next_question"]["category"], "current_status")
    assert_true("does not repeat branding question", "A ideia é melhorar posicionamento" not in step["reply"])


def test_branding_quero_fazer_os_dois_short_answer():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="Quero fazer os dois")
    assert_equal("main_goal", step["state_after"]["main_goal"], "posicionamento e conteúdo/redes sociais")
    assert_true("reply advances", "presença ativa" in step["reply"])


def test_traffic_three_points_short_answer():
    state = state_with_choice("service_traffic")
    state = sales_brain.merge_state(
        state,
        {
            "current_status": "começar do zero",
            "last_question_category": "main_goal",
            "last_question_asked": "O foco é gerar leads, vender no site ou fortalecer a marca?",
        },
    )
    step = pipeline_step(state, message="os 3 pontos")
    assert_equal("main_goal", step["state_after"]["main_goal"], "gerar leads, vender no site e fortalecer marca")
    assert_equal("next category", step["next_question"]["category"], "budget_signal")


def test_timeout_fallback_branding_does_not_repeat_literal():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="os dois")
    assert_true("fallback advanced", step["reply"] != "Legal. A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?")
    assert_equal("main_goal", step["state_after"]["main_goal"], "posicionamento e conteúdo/redes sociais")
    assert_equal("next category", step["next_question"]["category"], "current_status")
    assert_true("did not repeat branding question", "A ideia é melhorar posicionamento" not in step["reply"])


def test_traffic():
    state = state_with_choice("service_traffic")
    state = sales_brain.merge_state(state, {"last_question_category": "current_status"})
    state = apply_message(state, "já anuncio")
    assert_equal("current_status", sales_brain.flatten_state(state)["current_status"], "já anuncia")


def test_pipeline_traffic_zero():
    step1 = pipeline_step(
        sales_brain.default_lead_state(),
        list_title="Tráfego pago",
        list_description="Performance e anúncios",
    )
    state = step1["state_after"]
    assert_equal("service_interest", state["service_interest"], "trafego_pago")
    assert_equal("first category", step1["next_question"]["category"], "current_status")

    step2 = pipeline_step(state, message="começar do zero")
    state = step2["state_after"]
    assert_equal("current_status", state["current_status"], "começar do zero")
    assert_equal("next category", step2["next_question"]["category"], "main_goal")
    assert_true("no generic service question", "você procura site" not in step2["reply"].lower())


def test_pipeline_site_melhorar():
    step1 = pipeline_step(
        sales_brain.default_lead_state(),
        list_title="Site ou landing",
        list_description="Criar ou melhorar páginas",
    )
    state = step1["state_after"]
    assert_equal("service_interest", state["service_interest"], "site")
    assert_equal("first category", step1["next_question"]["category"], "site_scope")

    step2 = pipeline_step(state, message="melhorar uma pagina que ja existe")
    state = step2["state_after"]
    assert_equal("contextual answer is not menu", step2["normalized_choice"]["is_menu_choice"], False)
    assert_equal("site_scope", state["site_scope"], "melhorar existente")
    assert_equal("next category", step2["next_question"]["category"], "main_goal")
    assert_true("did not repeat site_scope", "página nova do zero" not in step2["reply"])


def test_persisted_pipeline_site_state_between_messages():
    store = {}
    wa_id = "5511999990000"
    first = persisted_pipeline_step(
        store,
        wa_id,
        list_title="Site ou landing",
        list_description="Criar ou melhorar páginas",
    )
    assert_equal("first state service", first["state_after"]["service_interest"], "site")
    assert_equal("first state category", first["state_after"]["last_question_category"], "site_scope")

    second = persisted_pipeline_step(store, wa_id, message="melhorar uma pagina que ja existe")
    assert_equal("second loaded service", second["state_before"]["service_interest"], "site")
    assert_equal("second loaded category", second["state_before"]["last_question_category"], "site_scope")
    assert_equal("contextual answer is not menu", second["normalized_choice"]["is_menu_choice"], False)
    assert_equal("signal site_scope", second["extracted_signals"]["site_scope"], "melhorar existente")
    assert_equal("state site_scope", second["state_after"]["site_scope"], "melhorar existente")
    assert_equal("next category", second["next_question"]["category"], "main_goal")
    assert_equal("reply", second["reply"], "Certo. Então estamos falando de melhorar uma página que já existe. O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?")


def test_dedupe_patch_preserves_sales_state():
    store = {}
    wa_id = "5511972769605"
    first = persisted_pipeline_step(
        store,
        wa_id,
        list_id="service_automation",
        list_title="Automatizar WhatsApp",
        list_description="Atendimento, leads e CRM",
    )
    store[wa_id] = dedupe_patch_state(first["state_after"], "wamid.test.1")
    second = persisted_pipeline_step(store, wa_id, message="WhatsApp")
    assert_equal("loaded service after dedupe", second["state_before"]["service_interest"], "automacao_whatsapp")
    assert_equal("loaded category after dedupe", second["state_before"]["last_question_category"], "lead_source")
    assert_equal("whatsapp is contextual", second["normalized_choice"]["is_menu_choice"], False)
    assert_equal("lead_source", second["state_after"]["lead_source"], "WhatsApp")
    assert_equal("next category", second["next_question"]["category"], "current_tools")


def test_ai_fields_do_not_turn_lead_source_into_current_tools():
    from app import _sanitize_ai_lead_fields

    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(
        state,
        {
            "last_question_category": "lead_source",
            "last_question_asked": "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?",
        },
    )
    signals = {"lead_source": "WhatsApp", "funnel_stage": "qualificacao"}
    sanitized = _sanitize_ai_lead_fields(
        {"lead_source": "WhatsApp", "current_tools": "WhatsApp", "main_goal": "Automatizar meu WhatsApp"},
        state_before=state,
        extracted_signals=signals,
        user_text="WhatsApp",
    )
    assert_equal("lead_source kept", sanitized.get("lead_source"), "WhatsApp")
    assert_equal("current_tools removed", sanitized.get("current_tools"), None)
    assert_equal("unrelated main_goal removed", sanitized.get("main_goal"), None)


def test_openai_fallback_is_marked():
    from services.openai_client import _fallback

    result = _fallback("Ok, muito obrigado")
    assert_equal("fallback marker", result.get("fallback"), True)


def test_deadline_urgency_triggers_handoff():
    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(
        state,
        {
            "lead_source": "WhatsApp",
            "current_tools": "manual",
            "current_problem": "processo manual",
            "last_question_category": "urgency",
        },
    )
    step = pipeline_step(state, message="Preciso disso rodando até dia 08/05")
    assert_equal("urgency", step["state_after"]["urgency"], "alta")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_equal("next_action", step["state_after"]["next_action"], "handoff")
    assert_equal("briefing_ready", step["state_after"]["briefing_ready"], True)


def test_ai_intent_cannot_switch_locked_service():
    from app import _sanitize_ai_lead_fields

    state = state_with_choice("service_automation")
    state = sales_brain.merge_state(state, {"last_question_category": "urgency"})
    sanitized = _sanitize_ai_lead_fields(
        {"intent": "inteligencia_artificial", "urgency": "alta"},
        state_before=state,
        extracted_signals={"urgency": "alta"},
        user_text="Preciso disso rodando até dia 08/05",
    )
    assert_equal("intent locked", sanitized.get("intent"), "automacao_whatsapp")


def test_post_handoff_julia_link_reply():
    from app import JULIA_DIRECT_LINK, _post_handoff_utility_reply

    reply = _post_handoff_utility_reply("Você vai me enviar o link para entrar em contato com Júlia?")
    assert_true("has Julia link", JULIA_DIRECT_LINK in reply)
    reply_question = _post_handoff_utility_reply("?")
    assert_true("question mark gets link", JULIA_DIRECT_LINK in reply_question)


def test_site_scope_not_overwritten_without_explicit_change():
    state = state_with_choice("service_site")
    state = sales_brain.merge_state(
        state,
        {
            "site_scope": "melhorar existente",
            "main_goal": "vendas/leads",
            "last_question_category": "urgency",
        },
    )
    step = pipeline_step(state, message="Preciso que vocês me ajudem a criar tudo, vocês conseguem?")
    assert_equal("site_scope kept", step["state_after"]["site_scope"], "melhorar existente")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_equal("briefing_ready", step["state_after"]["briefing_ready"], True)


def test_explicit_site_scope_change_allowed():
    state = state_with_choice("service_site")
    state = sales_brain.merge_state(state, {"site_scope": "melhorar existente", "last_question_category": "site_scope"})
    step = pipeline_step(state, message="na verdade quero criar do zero")
    assert_equal("site_scope changed", step["state_after"]["site_scope"], "criar do zero")


def test_handoff_reply_includes_julia_link():
    from app import JULIA_DIRECT_LINK, JULIA_HANDOFF_REPLY

    assert_true("handoff has link", JULIA_DIRECT_LINK in JULIA_HANDOFF_REPLY)
    assert_true("handoff has encoded text", "?text=" in JULIA_HANDOFF_REPLY)


def test_prefilled_julia_link_contains_encoded_context():
    from app import JULIA_DIRECT_LINK, build_julia_prefilled_link

    context = {
        "service_interest": "automacao_whatsapp",
        "main_goal": "responder leads mais rápido",
        "current_problem": "processo manual",
        "lead_source": "WhatsApp",
        "current_tools": "planilha",
        "urgency": "alta",
        "budget_signal": "tem verba",
        "briefing": {"summary": "Lead quer automatizar atendimento até maio."},
    }
    link = build_julia_prefilled_link(context)
    assert_true("link prefix", link.startswith(f"{JULIA_DIRECT_LINK}?text="))
    decoded = urllib.parse.unquote(link.split("?text=", 1)[1])
    assert_true("decoded service", "Serviço: automacao_whatsapp" in decoded)
    assert_true("decoded goal", "Objetivo: responder leads mais rápido" in decoded)
    assert_true("decoded problem", "Problema: processo manual" in decoded)
    assert_true("decoded budget", "Orçamento: tem verba" in decoded)
    assert_true("decoded summary", "Resumo:\nLead quer automatizar atendimento até maio." in decoded)


def test_internal_operation_briefing_without_link():
    from app import OPERATION_NUMBER, _build_julia_briefing_message

    result = {
        "lead_temperature": "hot",
        "lead_fields": {
            "service_interest": "site",
            "main_goal": "vendas/leads",
            "current_problem": "página antiga",
            "lead_source": "Instagram",
            "current_tools": "manual",
            "urgency": "alta",
        },
        "briefing": {"summary": "Lead quer melhorar a página atual para vender mais."},
    }
    message = _build_julia_briefing_message(wa_id="5511999999999", user={"nome": "Lead Teste"}, result=result)
    assert_equal("operation number", OPERATION_NUMBER, "5511972769605")
    assert_true("structured title", "🔥 Novo lead qualificado" in message)
    assert_true("service in message", "Serviço: site" in message)
    assert_true("summary in message", "Lead quer melhorar a página atual" in message)
    assert_true("no wa link", "wa.me" not in message)


def test_no_legacy_eduarda_routing():
    import app

    assert_true("no legacy Eduarda number", not hasattr(app, "EDUARDA_NUMBER"))


def test_handoff_opening_varies_from_last_reply():
    from app import build_handoff_lead_reply

    first = build_handoff_lead_reply({"last_question_asked": "Certo. Já deixei um resumo pronto para a Julia."})
    second = build_handoff_lead_reply({"last_question_asked": first})
    third = build_handoff_lead_reply({"last_question_asked": second})
    openings = [reply.split(".", 1)[0] for reply in [first, second, third]]
    assert_true("no same opening three times", len(set(openings)) > 1)


def test_followup_created_for_handoff():
    from app import HANDOFF_FOLLOWUP_MESSAGE, build_handoff_follow_up

    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    follow_up = build_handoff_follow_up(now)
    assert_equal("follow up needed", follow_up["needed"], True)
    assert_equal("follow up when", follow_up["when"], "2026-04-29T13:00:00+00:00")
    assert_equal("follow up message", follow_up["message"], HANDOFF_FOLLOWUP_MESSAGE)


def test_followup_due_once_only():
    from app import _followup_is_due

    now = datetime(2026, 4, 29, 13, 1, tzinfo=timezone.utc)
    state = {
        "follow_up": {
            "needed": True,
            "when": (now - timedelta(minutes=1)).isoformat(),
            "message": "follow",
        }
    }
    assert_equal("due before sent", _followup_is_due(state, now), True)
    state["handoff_followup_sent_at"] = now.isoformat()
    assert_equal("not due after sent", _followup_is_due(state, now), False)


def test_traffic_budget_handoff_reply_has_julia_link():
    from app import JULIA_DIRECT_LINK

    state = state_with_choice("service_traffic")
    state = sales_brain.merge_state(
        state,
        {
            "current_status": "já anuncia",
            "main_goal": "vendas/leads",
            "last_question_category": "budget_signal",
        },
    )
    step = pipeline_step(state, message="tenho verba")
    assert_equal("budget_signal", step["state_after"]["budget_signal"], "tem verba")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_true("reply has Julia link", JULIA_DIRECT_LINK in step["reply"])


def test_site_urgency_handoff_reply_has_julia_link():
    from app import JULIA_DIRECT_LINK

    state = state_with_choice("service_site")
    state = sales_brain.merge_state(
        state,
        {
            "site_scope": "melhorar existente",
            "main_goal": "vendas/leads",
            "last_question_category": "urgency",
        },
    )
    step = pipeline_step(state, message="essa semana")
    assert_equal("urgency", step["state_after"]["urgency"], "alta")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_true("reply has Julia link", JULIA_DIRECT_LINK in step["reply"])


def test_any_handoff_reply_without_link_is_corrected():
    from app import JULIA_DIRECT_LINK

    state = state_with_choice("service_automation")
    step = pipeline_step(
        state,
        message="quero falar com humano",
        ai_result={
            "reply": "Vou encaminhar para a Julia agora.",
            "next_action": "handoff",
            "handoff": True,
            "briefing_ready": True,
        },
    )
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_true("reply has Julia link", JULIA_DIRECT_LINK in step["reply"])


def test_no_three_perfeito_replies_in_flow():
    state = pipeline_step(sales_brain.default_lead_state(), list_id="service_site")["state_after"]
    replies = []
    for message in ["melhorar", "vendas", "essa semana"]:
        step = pipeline_step(state, message=message)
        replies.append(step["reply"])
        state = step["state_after"]
    starts = [reply.strip().lower().startswith("perfeito") for reply in replies]
    assert_true("not three perfeito starts", sum(starts) < 3)


def test_human():
    state = state_with_choice("service_human")
    flat = sales_brain.flatten_state(state)
    assert_equal("handoff", flat["handoff"], True)
    assert_equal("next_action", flat["next_action"], "handoff")


def test_anti_loop():
    state = state_with_choice("service_site")
    result = sales_brain.validate_final_reply(
        "Pra eu te direcionar melhor: a prioridade é página, WhatsApp, IA, anúncios ou marca?",
        state,
    )
    assert_equal("blocked", result["blocked"], True)
    assert_equal("reason", result["reason"], "forbidden_generic_reply")
    assert_equal("replacement category", result["category"], "site_scope")


def test_known_lead_source_blocks_repeat():
    state = state_with_choice("service_ai")
    state = sales_brain.merge_state(
        state,
        {
            "main_goal": "atendimento",
            "current_problem": "atendimento",
            "lead_source": "WhatsApp",
            "last_question_asked": "Hoje esses contatos chegam mais pelo WhatsApp, Instagram ou site?",
            "last_question_category": "lead_source",
        },
    )
    result = sales_brain.validate_final_reply("Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?", state)
    assert_equal("blocked", result["blocked"], True)
    assert_true("reason", result["reason"] in {"duplicate_last_question", "known_lead_source"})
    assert_equal("replacement category", result["category"], "current_tools")


def test_pipeline_anti_loop():
    state = state_with_choice("service_site")
    result = pipeline_step(
        state,
        message="site",
        forced_reply="Pra eu te direcionar melhor: você procura site, automação, IA, tráfego ou branding?",
    )
    assert_true("blocked generic", result["reply"] != "Pra eu te direcionar melhor: você procura site, automação, IA, tráfego ou branding?")
    assert_equal("replacement category", result["next_question"]["category"], "site_scope")


def main():
    tests = [
        ("menu_site", test_menu_site),
        ("site_melhorar", test_site_melhorar),
        ("site_do_zero", test_site_do_zero),
        ("site_melhorar_frase", test_site_melhorar_frase),
        ("text_site_without_state_is_menu", test_text_site_without_state_is_menu),
        ("text_site_with_state_is_not_menu", test_text_site_with_state_is_not_menu),
        ("automation_choice", test_automation_choice),
        ("all_service_buttons", test_all_service_buttons),
        ("pipeline_automation_contextual_answers", test_pipeline_automation_contextual_answers),
        ("real_meta_list_reply_automation_payload", test_real_meta_list_reply_automation_payload),
        ("ai_led_after_menu_choice", test_ai_led_after_menu_choice),
        ("ai_repeat_is_blocked", test_ai_repeat_is_blocked),
        ("urgency_triggers_julia_handoff", test_urgency_triggers_julia_handoff),
        ("julia_number_normalization", test_julia_number_normalization),
        ("operation_number_normalization", test_operation_number_normalization),
        ("operation_briefing_numbers_include_both", test_operation_briefing_numbers_include_both),
        ("automation_leads", test_automation_leads),
        ("manual", test_manual),
        ("ai_context", test_ai_context),
        ("pipeline_ai_full_flow", test_pipeline_ai_full_flow),
        ("ai_three_channels_short_answer", test_ai_three_channels_short_answer),
        ("branding_os_dois_short_answer", test_branding_os_dois_short_answer),
        ("branding_quero_fazer_os_dois_short_answer", test_branding_quero_fazer_os_dois_short_answer),
        ("traffic", test_traffic),
        ("traffic_three_points_short_answer", test_traffic_three_points_short_answer),
        ("timeout_fallback_branding_does_not_repeat_literal", test_timeout_fallback_branding_does_not_repeat_literal),
        ("pipeline_traffic_zero", test_pipeline_traffic_zero),
        ("pipeline_site_melhorar", test_pipeline_site_melhorar),
        ("persisted_pipeline_site_state_between_messages", test_persisted_pipeline_site_state_between_messages),
        ("dedupe_patch_preserves_sales_state", test_dedupe_patch_preserves_sales_state),
        ("ai_fields_do_not_turn_lead_source_into_current_tools", test_ai_fields_do_not_turn_lead_source_into_current_tools),
        ("openai_fallback_is_marked", test_openai_fallback_is_marked),
        ("deadline_urgency_triggers_handoff", test_deadline_urgency_triggers_handoff),
        ("ai_intent_cannot_switch_locked_service", test_ai_intent_cannot_switch_locked_service),
        ("post_handoff_julia_link_reply", test_post_handoff_julia_link_reply),
        ("site_scope_not_overwritten_without_explicit_change", test_site_scope_not_overwritten_without_explicit_change),
        ("explicit_site_scope_change_allowed", test_explicit_site_scope_change_allowed),
        ("handoff_reply_includes_julia_link", test_handoff_reply_includes_julia_link),
        ("prefilled_julia_link_contains_encoded_context", test_prefilled_julia_link_contains_encoded_context),
        ("internal_operation_briefing_without_link", test_internal_operation_briefing_without_link),
        ("no_legacy_eduarda_routing", test_no_legacy_eduarda_routing),
        ("handoff_opening_varies_from_last_reply", test_handoff_opening_varies_from_last_reply),
        ("followup_created_for_handoff", test_followup_created_for_handoff),
        ("followup_due_once_only", test_followup_due_once_only),
        ("traffic_budget_handoff_reply_has_julia_link", test_traffic_budget_handoff_reply_has_julia_link),
        ("site_urgency_handoff_reply_has_julia_link", test_site_urgency_handoff_reply_has_julia_link),
        ("any_handoff_reply_without_link_is_corrected", test_any_handoff_reply_without_link_is_corrected),
        ("no_three_perfeito_replies_in_flow", test_no_three_perfeito_replies_in_flow),
        ("human", test_human),
        ("anti_loop", test_anti_loop),
        ("known_lead_source_blocks_repeat", test_known_lead_source_blocks_repeat),
        ("pipeline_anti_loop", test_pipeline_anti_loop),
    ]
    for name, fn in tests:
        run_test(name, fn)
    print("ALL SALES FLOW TESTS PASSED")


if __name__ == "__main__":
    main()
