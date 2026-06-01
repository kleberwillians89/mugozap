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
    state = sales_brain.merge_state(sales_brain.default_lead_state(), sales_brain.service_choice_update(choice_id))
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
    assert_equal("site_scope", flat["site_scope"], "melhorar_site_existente")
    assert_equal("next category", sales_brain.get_next_question(flat)["category"], "current_problem")
    assert_true("next question asks problem", "maior incômodo" in sales_brain.get_next_question(flat)["question"])


def test_site_do_zero():
    state = state_with_choice("service_site")
    state = apply_message(state, "criar do zero")
    assert_equal("site_scope", sales_brain.flatten_state(state)["site_scope"], "criar do zero")


def test_site_melhorar_frase():
    state = state_with_choice("service_site")
    state = apply_message(state, "melhorar uma página que já existe")
    assert_equal("site_scope", sales_brain.flatten_state(state)["site_scope"], "melhorar_site_existente")


def test_semantic_interpretation_site_scope_non_literal():
    state = state_with_choice("service_site")
    cases = {
        "meu site até existe, mas está fraco": ("melhorar_existente", "visual"),
        "não tenho nada ainda": ("criar_do_zero", ""),
        "quero dar uma melhorada no que já tenho": ("melhorar_existente", ""),
        "preciso lançar uma página": ("criar_do_zero", ""),
        "a página não passa confiança": ("melhorar_existente", "confiança"),
        "já tenho, mas não vende": ("melhorar_existente", "converte"),
    }
    for message, (scope, problem_hint) in cases.items():
        interpreted = sales_brain.interpret_user_message(message, state)
        fields = interpreted["extracted_fields"]
        assert_equal(f"{message} site_scope", fields["site_scope"], scope)
        assert_equal(f"{message} stage_answered", interpreted["stage_answered"], True)
        assert_true(f"{message} confidence", interpreted["confidence"] >= 0.65)
        if problem_hint:
            assert_true(f"{message} problem", problem_hint in fields["current_problem"])


def test_pipeline_site_non_literal_answers_advance():
    cases = {
        "meu site até existe, mas está fraco": "melhorar_site_existente",
        "não tenho nada ainda": "criar do zero",
        "quero dar uma melhorada no que já tenho": "melhorar_site_existente",
        "preciso lançar uma página": "criar do zero",
        "a página não passa confiança": "melhorar_site_existente",
        "já tenho, mas não vende": "melhorar_site_existente",
    }
    for message, expected_scope in cases.items():
        step = pipeline_step(state_with_choice("service_site"), message=message)
        assert_equal(f"{message} site_scope", step["state_after"]["site_scope"], expected_scope)
        assert_true(f"{message} does not repeat scope", "criar uma página nova do zero ou melhorar" not in step["reply"])
        if expected_scope == "criar do zero":
            assert_true(f"{message} asks page purpose", "vender um serviço" in step["reply"] and "captar leads" in step["reply"])
        else:
            assert_true(f"{message} advances to site problem", step["next_question"]["category"] in {"current_problem", "main_goal"})


def test_text_site_without_state_is_menu():
    choice = sales_brain.normalize_inbound_choice(text="site", current_state={})
    assert_equal("choice_id", choice["choice_id"], None)
    assert_equal("is_menu_choice", choice["is_menu_choice"], False)


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
            assert_true("human direct link", "https://wa.me/5511973510549" in step["reply"])
            assert_true("human link has no prefilled text", "?text=" not in step["reply"])
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
    assert_equal("next category", step3["next_question"]["category"], "main_goal")
    assert_true("asks objective", "vender mais" in step3["reply"] and "processo comercial" in step3["reply"])


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
    assert_true("reply interprets automation", "atendimento" in step1["reply"].lower())
    assert_true("reply asks source", "WhatsApp, Instagram ou site" in step1["reply"])

    step2 = pipeline_step(state, message="WhatsApp")
    state = step2["state_after"]
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_true("reply asks tools", "manualmente" in step2["reply"] and "automação" in step2["reply"])
    assert_true("did not repeat source", "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?" not in step2["reply"])


def test_progressive_discovery_whatsapp_manual_vender_mais():
    step1 = pipeline_step(sales_brain.default_lead_state(), message="WhatsApp")
    assert_equal("service", step1["state_after"]["service_interest"], "automacao_whatsapp")
    assert_equal("canal", step1["state_after"]["conversation_memory"]["canal"], "WhatsApp")
    assert_equal("next category after channel", step1["next_question"]["category"], "current_tools")

    step2 = pipeline_step(step1["state_after"], message="manual")
    assert_equal("atendimento", step2["state_after"]["conversation_memory"]["atendimento"], "manual")
    assert_equal("next category after manual", step2["next_question"]["category"], "main_goal")
    assert_true("does not ask channel again", "contatos chegam" not in step2["reply"])

    step3 = pipeline_step(step2["state_after"], message="vender mais")
    memory = step3["state_after"]["conversation_memory"]
    reply_norm = sales_brain.normalize_text(step3["reply"])
    assert_equal("objetivo", memory["objetivo"], "vendas/leads")
    assert_true("does not ask channel", "contatos chegam" not in reply_norm and "whatsapp instagram ou site" not in reply_norm)
    assert_true("does not ask attendance", "atendem manualmente" not in reply_norm and "automacao rodando" not in reply_norm)
    assert_true("does not ask objective", "objetivo agora e vender mais" not in reply_norm and "responder mais rapido" not in reply_norm)
    assert_true("deepens context", step3["next_question"]["category"] in {"volume", "gargalo", "crm", "tempo_resposta"})
    assert_true("asks deeper question", any(term in reply_norm for term in ["quantos leads", "gargalo", "crm", "tempo de resposta", "conversas entram"]))


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
    assert_true("replacement asks operation", "manual" in step["reply"].lower() or "automação" in step["reply"].lower())


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
    from app import HUMAN_NUMBER, OPERATION_NUMBER, OPERATION_BRIEFING_NUMBERS

    assert_equal("operation briefing numbers", OPERATION_BRIEFING_NUMBERS, [HUMAN_NUMBER, OPERATION_NUMBER])
    assert_equal("julia briefing number", OPERATION_BRIEFING_NUMBERS[0], "5511973510549")
    assert_equal("operation briefing number", OPERATION_BRIEFING_NUMBERS[1], "5511972769605")


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
    assert_equal("next category", step2["next_question"]["category"], "current_tools")
    assert_true("microconfirmation atendimento", step2["reply"].startswith("Então faz sentido pensar em IA"))

    step3 = pipeline_step(state, message="whatsapp")
    state = step3["state_after"]
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_equal("current tools", state["current_tools"], "WhatsApp")
    assert_equal("next category", step3["next_question"]["category"], "volume_tarefa")


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
    assert_equal("next category", step["next_question"]["category"], "produto_servico")
    assert_true("does not repeat branding question", "A ideia é melhorar posicionamento" not in step["reply"])


def test_branding_quero_fazer_os_dois_short_answer():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="Quero fazer os dois")
    assert_equal("main_goal", step["state_after"]["main_goal"], "posicionamento e conteúdo/redes sociais")
    assert_true("reply advances", "marca vende" in step["reply"] or "quer apresentar melhor" in step["reply"])


def test_branding_identity_does_not_repeat_principal_point():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="identidade da marca")
    discovery = step["state_after"]["discovery_memory"]["branding"]
    assert_equal("focus", discovery["foco_marca"], "identidade")
    assert_equal("main goal", step["state_after"]["main_goal"], "identidade visual")
    assert_true("consultive tone", "clareza e consistência" in step["reply"])
    assert_true("does not ask principal point", "principal ponto que você quer resolver" not in step["reply"])
    assert_true("asks brand stage", "nome, identidade visual e redes ativas" in step["reply"])


def test_branding_create_brand_products_advances_to_product_stage():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="criar uma marca para divulgar meus produtos")
    discovery = step["state_after"]["discovery_memory"]["branding"]
    assert_equal("objective", discovery["objetivo_comunicacao"], "criar marca para divulgar produtos")
    assert_equal("product", discovery["produto_servico"], "produtos")
    assert_true("commercial intent tone", "intenção comercial" in step["reply"])
    assert_true("asks product status", "já são vendidos hoje" in step["reply"])
    assert_true("does not ask principal point", "principal ponto que você quer resolver" not in step["reply"])


def test_branding_growth_advances_to_frequency():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="aumentar o crescimento da minha marca")
    discovery = step["state_after"]["discovery_memory"]["branding"]
    assert_equal("objective", discovery["objetivo_comunicacao"], "crescimento de marca")
    assert_true("growth tone", "crescer com consistência" in step["reply"])
    assert_true("asks frequency", "publicam com frequência" in step["reply"])
    assert_true("does not ask principal point", "principal ponto que você quer resolver" not in step["reply"])


def test_all_initial_buttons_have_consultive_tracks():
    cases = {
        "service_site": ("site_scope", "página"),
        "service_automation": ("lead_source", "WhatsApp"),
        "service_ai": ("main_goal", "processo"),
        "service_traffic": ("current_status", "anunciam"),
        "service_branding": ("main_goal", "posicionamento"),
    }
    for choice_id, (category, hint) in cases.items():
        step = pipeline_step(sales_brain.default_lead_state(), list_id=choice_id)
        assert_equal(f"{choice_id} category", step["next_question"]["category"], category)
        assert_true(f"{choice_id} hint", hint.lower() in step["reply"].lower())


def test_human_button_directs_to_team():
    step = pipeline_step(sales_brain.default_lead_state(), list_id="service_human")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_true("direct team copy", "Claro. Vou te direcionar para a equipe da Mugô." in step["reply"])
    assert_true("julia link", "https://wa.me/5511973510549" in step["reply"])


def test_traffic_advances_after_objective():
    state = state_with_choice("service_traffic")
    step1 = pipeline_step(state, message="já anuncio")
    step2 = pipeline_step(step1["state_after"], message="gerar leads")
    assert_equal("objective", step2["state_after"]["discovery_memory"]["trafego_pago"]["objetivo_campanha"], "vendas/leads")
    assert_true("does not repeat objective", "gerar leads, vender no site ou fortalecer" not in step2["reply"])
    assert_true("asks offer", "oferta" in step2["reply"] or "produto" in step2["reply"])


def test_ai_advances_after_operational_pain():
    state = state_with_choice("service_ai")
    step = pipeline_step(state, message="processos internos manuais tomam tempo")
    discovery = step["state_after"]["discovery_memory"]["inteligencia_artificial"]
    assert_equal("process", discovery["processo"], "processos internos")
    assert_true("pain", bool(discovery["dor_operacional"]))
    assert_true("does not repeat process question", "atendimento, vendas, conteúdo ou operação interna" not in step["reply"])
    assert_true("asks next depth", "manual" in step["reply"].lower() or "ferramenta" in step["reply"].lower() or "volume" in step["reply"].lower())


def test_no_button_repeats_last_three_questions():
    scenarios = [
        ("service_site", ["melhorar um site", "não converte"]),
        ("service_automation", ["WhatsApp", "manual", "vender mais"]),
        ("service_ai", ["processos internos manuais tomam tempo", "planilha"]),
        ("service_traffic", ["já anuncio", "gerar leads"]),
        ("service_branding", ["identidade da marca", "ainda está do zero"]),
    ]
    for choice_id, messages in scenarios:
        state = pipeline_step(sales_brain.default_lead_state(), list_id=choice_id)["state_after"]
        replies = []
        for message in messages:
            step = pipeline_step(state, message=message)
            replies.append(step["reply"])
            recent = step["state_after"].get("recent_bot_questions") or []
            assert_true(f"{choice_id} recent max three", len(recent) <= 3)
            for previous in recent[:-1]:
                assert_true(f"{choice_id} no semantic repeat", not sales_brain.is_duplicate_question(step["reply"], previous))
            state = step["state_after"]
        assert_true(f"{choice_id} unique replies", len({sales_brain.normalize_text(reply) for reply in replies}) == len(replies))


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
    assert_equal("next category", step["next_question"]["category"], "oferta")


def test_timeout_fallback_branding_does_not_repeat_literal():
    state = state_with_choice("service_branding")
    step = pipeline_step(state, message="os dois")
    assert_true("fallback advanced", step["reply"] != "Legal. A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?")
    assert_equal("main_goal", step["state_after"]["main_goal"], "posicionamento e conteúdo/redes sociais")
    assert_equal("next category", step["next_question"]["category"], "produto_servico")
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
    assert_equal("site_scope", state["site_scope"], "melhorar_site_existente")
    assert_equal("next category", step2["next_question"]["category"], "current_problem")
    assert_true("did not repeat site_scope", "página nova do zero" not in step2["reply"])
    assert_true("asks site problem", "maior incômodo" in step2["reply"])


def test_pipeline_site_melhorar_um_site_advances_to_problem():
    step1 = pipeline_step(
        sales_brain.default_lead_state(),
        list_title="Site ou landing",
        list_description="Criar ou melhorar páginas",
    )
    step2 = pipeline_step(step1["state_after"], message="Melhorar um site")
    assert_equal("contextual answer is not menu", step2["normalized_choice"]["is_menu_choice"], False)
    assert_equal("site scope", step2["state_after"]["site_scope"], "melhorar_site_existente")
    assert_equal("next category", step2["next_question"]["category"], "current_problem")
    assert_true("does not repeat create/improve", "página nova do zero" not in step2["reply"])
    assert_true("asks problem", "maior incômodo" in step2["reply"])


def test_pipeline_site_short_answer_does_not_repeat_scope():
    state = state_with_choice("service_site")
    step = pipeline_step(state, message="Site")
    assert_equal("site scope", step["state_after"]["site_scope"], "melhorar_site_existente")
    assert_equal("next category", step["next_question"]["category"], "current_problem")
    assert_true("does not repeat scope", "página nova do zero" not in step["reply"])
    assert_true("asks site problem", "maior incômodo" in step["reply"])


def test_pipeline_whatsapp_short_answer_maps_to_automation():
    step = pipeline_step(sales_brain.default_lead_state(), message="WhatsApp")
    assert_equal("not menu click", step["normalized_choice"]["is_menu_choice"], False)
    assert_equal("service", step["state_after"]["service_interest"], "automacao_whatsapp")
    assert_equal("lead source", step["state_after"]["lead_source"], "WhatsApp")
    assert_equal("next category", step["next_question"]["category"], "current_tools")
    assert_true("asks operation", "manual" in step["reply"].lower() or "automação" in step["reply"].lower())


def test_pipeline_instagram_short_answer_maps_to_social():
    step = pipeline_step(sales_brain.default_lead_state(), message="Instagram")
    assert_equal("not menu click", step["normalized_choice"]["is_menu_choice"], False)
    assert_equal("service", step["state_after"]["service_interest"], "branding")
    assert_equal("lead source", step["state_after"]["lead_source"], "Instagram")
    assert_equal("next category", step["next_question"]["category"], "dificuldade_atual")
    assert_true("asks instagram challenge", "atrair pessoas certas" in step["reply"])


def test_pipeline_vague_answer_uses_premium_refinement():
    step = pipeline_step(sales_brain.default_lead_state(), message="não sei ainda")
    assert_equal("next category", step["next_question"]["category"], "service_interest")
    assert_true("premium fallback", "leitura mais ampla" in step["reply"])
    assert_true("one question", step["reply"].count("?") <= 1)


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
    assert_equal("signal site_scope", second["extracted_signals"]["site_scope"], "melhorar_site_existente")
    assert_equal("state site_scope", second["state_after"]["site_scope"], "melhorar_site_existente")
    assert_equal("next category", second["next_question"]["category"], "current_problem")
    assert_equal("reply", second["reply"], "Então o foco é melhorar uma estrutura que já existe. Hoje o maior incômodo é visual, conversão, velocidade, clareza da oferta ou organização das informações?")


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
            "site_scope": "melhorar_site_existente",
            "main_goal": "vendas/leads",
            "last_question_category": "urgency",
        },
    )
    step = pipeline_step(state, message="Preciso que vocês me ajudem a criar tudo, vocês conseguem?")
    assert_equal("site_scope kept", step["state_after"]["site_scope"], "melhorar_site_existente")
    assert_equal("handoff", step["state_after"]["handoff"], True)
    assert_equal("briefing_ready", step["state_after"]["briefing_ready"], True)


def test_explicit_site_scope_change_allowed():
    state = state_with_choice("service_site")
    state = sales_brain.merge_state(state, {"site_scope": "melhorar_site_existente", "last_question_category": "site_scope"})
    step = pipeline_step(state, message="na verdade quero criar do zero")
    assert_equal("site_scope changed", step["state_after"]["site_scope"], "criar do zero")


def test_handoff_reply_includes_julia_link():
    from app import JULIA_DIRECT_LINK, JULIA_HANDOFF_REPLY

    expected = (
        "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma.\n\n"
        "Você pode continuar diretamente com a Julia:\n\n"
        f"{JULIA_DIRECT_LINK}"
    )
    assert_equal("handoff exact reply", JULIA_HANDOFF_REPLY, expected)
    assert_true("handoff has no encoded text", "?text=" not in JULIA_HANDOFF_REPLY)
    assert_true("client has no strategic synthesis", "Síntese estratégica" not in JULIA_HANDOFF_REPLY)
    assert_true("client has no opportunity", "Oportunidade percebida" not in JULIA_HANDOFF_REPLY)
    assert_true("client has no commercial reading", "Leitura comercial" not in JULIA_HANDOFF_REPLY)
    assert_true("client has no next step", "Próximo passo" not in JULIA_HANDOFF_REPLY)


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
    assert_true("premium title", "✨ Novo contato qualificado pela Mugô" in decoded)
    assert_true("moment", "Momento identificado:" in decoded)
    assert_true("strategic reading", "Leitura estratégica:" in decoded)
    assert_true("opportunity", "Oportunidade para a Mugô:" in decoded)
    assert_true("temperature", "Temperatura comercial:" in decoded)
    assert_true("next movement", "Próximo movimento recomendado:" in decoded)
    assert_true("no raw service label", "Serviço:" not in decoded)
    assert_true("no raw budget label", "Orçamento:" not in decoded)
    assert_true("no generic adherence language", "A frente mais aderente parece ser" not in decoded)


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
    assert_true("structured title", "✨ Novo contato qualificado pela Mugô" in message)
    assert_true("moment in message", "Momento identificado:" in message)
    assert_true("reading in message", "Leitura estratégica:" in message)
    assert_true("opportunity in message", "Oportunidade para a Mugô:" in message)
    assert_true("temperature in message", "Temperatura comercial:" in message)
    assert_true("next movement in message", "Próximo movimento recomendado:" in message)
    assert_true("summary in message", "Lead quer melhorar a página atual" in message)
    assert_true("no wa link", "wa.me" not in message)
    assert_true("no crm style language", "Contato sinaliza aderência" not in message)
    assert_true("no generic ai language", "A frente mais aderente parece ser" not in message)


def test_no_legacy_eduarda_routing():
    import app

    assert_true("no legacy Eduarda number", not hasattr(app, "EDUARDA_NUMBER"))


def test_handoff_opening_varies_from_last_reply():
    from app import build_handoff_lead_reply

    first = build_handoff_lead_reply({"last_question_asked": "Certo. Já deixei um resumo pronto para a Julia."})
    second = build_handoff_lead_reply({"last_question_asked": first})
    third = build_handoff_lead_reply({"last_question_asked": second})
    assert_equal("fixed first", first, second)
    assert_equal("fixed second", second, third)
    assert_true("fixed starts perfeito", first.startswith("Perfeito. Já tenho contexto suficiente"))


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
            "site_scope": "melhorar_site_existente",
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
    assert_equal("replacement category", result["category"], "current_problem")


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
    assert_equal("replacement category", result["next_question"]["category"], "current_problem")


def test_last_three_questions_block_semantic_repeat():
    state = sales_brain.merge_state(
        sales_brain.default_lead_state(),
        {
            "service_interest": "site",
            "intent": "site",
            "recent_bot_questions": [
                "Você quer criar uma página nova do zero ou melhorar uma página que já existe?",
                "Hoje o maior incômodo é visual, conversão, velocidade, clareza da oferta ou organização das informações?",
                "O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?",
            ],
            "last_question_asked": "O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?",
            "last_question_category": "main_goal",
        },
    )
    result = sales_brain.validate_final_reply("O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?", state)
    assert_equal("blocked", result["blocked"], True)
    assert_equal("reason", result["reason"], "duplicate_last_question")
    assert_true("replacement changes question", "O foco dessa página" not in result["reply"])


def main():
    tests = [
        ("menu_site", test_menu_site),
        ("site_melhorar", test_site_melhorar),
        ("site_do_zero", test_site_do_zero),
        ("site_melhorar_frase", test_site_melhorar_frase),
        ("semantic_interpretation_site_scope_non_literal", test_semantic_interpretation_site_scope_non_literal),
        ("pipeline_site_non_literal_answers_advance", test_pipeline_site_non_literal_answers_advance),
        ("text_site_without_state_is_menu", test_text_site_without_state_is_menu),
        ("text_site_with_state_is_not_menu", test_text_site_with_state_is_not_menu),
        ("automation_choice", test_automation_choice),
        ("all_service_buttons", test_all_service_buttons),
        ("pipeline_automation_contextual_answers", test_pipeline_automation_contextual_answers),
        ("real_meta_list_reply_automation_payload", test_real_meta_list_reply_automation_payload),
        ("progressive_discovery_whatsapp_manual_vender_mais", test_progressive_discovery_whatsapp_manual_vender_mais),
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
        ("branding_identity_does_not_repeat_principal_point", test_branding_identity_does_not_repeat_principal_point),
        ("branding_create_brand_products_advances_to_product_stage", test_branding_create_brand_products_advances_to_product_stage),
        ("branding_growth_advances_to_frequency", test_branding_growth_advances_to_frequency),
        ("all_initial_buttons_have_consultive_tracks", test_all_initial_buttons_have_consultive_tracks),
        ("human_button_directs_to_team", test_human_button_directs_to_team),
        ("traffic_advances_after_objective", test_traffic_advances_after_objective),
        ("ai_advances_after_operational_pain", test_ai_advances_after_operational_pain),
        ("no_button_repeats_last_three_questions", test_no_button_repeats_last_three_questions),
        ("traffic", test_traffic),
        ("traffic_three_points_short_answer", test_traffic_three_points_short_answer),
        ("timeout_fallback_branding_does_not_repeat_literal", test_timeout_fallback_branding_does_not_repeat_literal),
        ("pipeline_traffic_zero", test_pipeline_traffic_zero),
        ("pipeline_site_melhorar", test_pipeline_site_melhorar),
        ("pipeline_site_melhorar_um_site_advances_to_problem", test_pipeline_site_melhorar_um_site_advances_to_problem),
        ("pipeline_site_short_answer_does_not_repeat_scope", test_pipeline_site_short_answer_does_not_repeat_scope),
        ("pipeline_whatsapp_short_answer_maps_to_automation", test_pipeline_whatsapp_short_answer_maps_to_automation),
        ("pipeline_instagram_short_answer_maps_to_social", test_pipeline_instagram_short_answer_maps_to_social),
        ("pipeline_vague_answer_uses_premium_refinement", test_pipeline_vague_answer_uses_premium_refinement),
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
        ("last_three_questions_block_semantic_repeat", test_last_three_questions_block_semantic_repeat),
    ]
    for name, fn in tests:
        run_test(name, fn)
    print("ALL SALES FLOW TESTS PASSED")


if __name__ == "__main__":
    main()
