from __future__ import annotations

import sys
from pathlib import Path

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
    reply = forced_reply or sales_brain.build_contextual_reply(state_before, state_after, signals, next_q)
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
        "used_openai": False,
    }


def persisted_pipeline_step(store: dict, wa_id: str, **kwargs) -> dict:
    state = store.get(wa_id) or sales_brain.default_lead_state()
    result = pipeline_step(state, **kwargs)
    store[wa_id] = result["state_after"]
    return result


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
    assert_true("microconfirmation atendimento", step2["reply"].startswith("Perfeito. Então faz sentido pensar em IA"))

    step3 = pipeline_step(state, message="whatsapp")
    state = step3["state_after"]
    assert_equal("lead_source", state["lead_source"], "WhatsApp")
    assert_equal("next category", step3["next_question"]["category"], "current_tools")
    assert_true("did not repeat lead source", "Hoje os contatos chegam mais" not in step3["reply"])
    assert_true("microconfirmation whatsapp", step3["reply"].startswith("Boa. Então o WhatsApp é o principal canal."))

    step4 = pipeline_step(state, message="manualmente")
    state = step4["state_after"]
    assert_equal("current_tools", state["current_tools"], "manual")
    assert_equal("next category", step4["next_question"]["category"], "urgency")
    assert_true("microconfirmation manual", step4["reply"].startswith("Entendi. Aí a automação pode ajudar"))

    step5 = pipeline_step(state, message="essa semana")
    state = step5["state_after"]
    if sales_brain.should_offer_meeting(state):
        state = sales_brain.merge_state(state, {"meeting_suggested": True, "briefing_ready": True})
    assert_equal("urgency", state["urgency"], "alta")
    assert_equal("meeting_suggested", state["meeting_suggested"], True)
    assert_equal("briefing_ready", state["briefing_ready"], True)


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
    assert_equal("reply", second["reply"], "Perfeito. Então estamos falando de melhorar uma página que já existe. O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?")


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
        ("pipeline_automation_contextual_answers", test_pipeline_automation_contextual_answers),
        ("real_meta_list_reply_automation_payload", test_real_meta_list_reply_automation_payload),
        ("automation_leads", test_automation_leads),
        ("manual", test_manual),
        ("ai_context", test_ai_context),
        ("pipeline_ai_full_flow", test_pipeline_ai_full_flow),
        ("traffic", test_traffic),
        ("pipeline_traffic_zero", test_pipeline_traffic_zero),
        ("pipeline_site_melhorar", test_pipeline_site_melhorar),
        ("persisted_pipeline_site_state_between_messages", test_persisted_pipeline_site_state_between_messages),
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
