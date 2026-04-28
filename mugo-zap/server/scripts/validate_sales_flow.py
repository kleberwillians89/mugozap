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
    state = apply_message(state, "melhorar")
    flat = sales_brain.flatten_state(state)
    assert_equal("site_scope", flat["site_scope"], "melhorar existente")
    assert_equal("next category", sales_brain.get_next_question(flat)["category"], "main_goal")


def test_site_do_zero():
    state = state_with_choice("service_site")
    state = apply_message(state, "criar do zero")
    assert_equal("site_scope", sales_brain.flatten_state(state)["site_scope"], "criar do zero")


def test_automation_choice():
    state = state_with_choice("service_automation")
    flat = sales_brain.flatten_state(state)
    assert_equal("service_interest", flat["service_interest"], "automacao_whatsapp")
    assert_equal("next category", sales_brain.get_next_question(flat)["category"], "lead_source")


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


def test_traffic():
    state = state_with_choice("service_traffic")
    state = sales_brain.merge_state(state, {"last_question_category": "current_status"})
    state = apply_message(state, "já anuncio")
    assert_equal("current_status", sales_brain.flatten_state(state)["current_status"], "já anuncia")


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


def main():
    tests = [
        ("menu_site", test_menu_site),
        ("site_melhorar", test_site_melhorar),
        ("site_do_zero", test_site_do_zero),
        ("automation_choice", test_automation_choice),
        ("automation_leads", test_automation_leads),
        ("manual", test_manual),
        ("ai_context", test_ai_context),
        ("traffic", test_traffic),
        ("human", test_human),
        ("anti_loop", test_anti_loop),
    ]
    for name, fn in tests:
        run_test(name, fn)
    print("ALL SALES FLOW TESTS PASSED")


if __name__ == "__main__":
    main()
