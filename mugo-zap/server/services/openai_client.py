from typing import Any, Dict, Optional

from services.state import (
    get_flow,
    set_flow_state,
    merge_flow_data,
    clear_flow,
    set_notes,
    set_stage,
)

# TITLES <= 20 chars (senão a Meta rejeita)
MENU_MAIN = [
    {"id": "FLOW_AUTOMATIZAR", "title": "⚙️ Automação"},
    {"id": "FLOW_SITE", "title": "🌐 Site / Loja"},
    {"id": "FLOW_SOCIAL", "title": "📈 Social/Tráfego"},
]

AUTOMACAO_MENU = [
    {"id": "AUTO_ATEND", "title": "💬 WhatsApp"},
    {"id": "AUTO_CRM", "title": "📌 CRM/Funil"},
    {"id": "AUTO_FIN", "title": "💳 Cobrança"},
]

SITE_MENU = [
    {"id": "SITE_INST", "title": "🏢 Institucional"},
    {"id": "SITE_LP", "title": "🎯 Landing page"},
    {"id": "SITE_LOJA", "title": "🛒 Loja virtual"},
]

SOCIAL_MENU = [
    {"id": "SOC_CONT", "title": "✍️ Conteúdo"},
    {"id": "SOC_GEST", "title": "🧠 Gestão"},
    {"id": "SOC_TRAFEGO", "title": "📣 Tráfego pago"},
]

CTA_BTNS = [
    {"id": "CTA_HUMAN", "title": "🤝 Especialista"},
    {"id": "CTA_PROP", "title": "📩 Proposta"},
]

def _is_menu_reset(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in ("menu", "inicio", "início", "voltar", "volta")

def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}

    text = (user_text or "").strip()
    cid = (choice_id or "").strip() or text

    # reset/menu
    if _is_menu_reset(text):
        set_flow_state(wa_id, "main")
        return {"type": "buttons", "text": "Qual é o foco agora?", "buttons": MENU_MAIN}

    # se não tem state, começa com menu
    if not state:
        set_flow_state(wa_id, "main")
        return {"type": "buttons", "text": "Oi! O que você quer destravar agora?", "buttons": MENU_MAIN}

    # ========= MAIN =========
    if state == "main":
        if cid == "FLOW_AUTOMATIZAR":
            merge_flow_data(wa_id, {"macro": "automacao"})
            set_flow_state(wa_id, "automacao_menu")
            return {"type": "buttons", "text": "O que você quer automatizar primeiro?", "buttons": AUTOMACAO_MENU}

        if cid == "FLOW_SITE":
            merge_flow_data(wa_id, {"macro": "site"})
            set_flow_state(wa_id, "site_menu")
            return {"type": "buttons", "text": "Que tipo de projeto você quer?", "buttons": SITE_MENU}

        if cid == "FLOW_SOCIAL":
            merge_flow_data(wa_id, {"macro": "social"})
            set_flow_state(wa_id, "social_menu")
            return {"type": "buttons", "text": "O que você precisa no social?", "buttons": SOCIAL_MENU}

        return {"type": "buttons", "text": "Escolhe uma opção pra eu te guiar:", "buttons": MENU_MAIN}

    # ========= SUBMENUS =========
    if state in ("automacao_menu", "site_menu", "social_menu"):
        # se clicou em algo válido
        valid_ids = {b["id"] for b in (AUTOMACAO_MENU + SITE_MENU + SOCIAL_MENU)}
        if cid in valid_ids:
            merge_flow_data(wa_id, {"service_interest": cid})
            set_flow_state(wa_id, "brief")
            return {"type": "text", "text": "Em 1 frase: o que você quer resolver agora?"}

        # se mandou texto em vez de clicar: ajuda com IA depois, mas mantém menu
        return {"type": "buttons", "text": "Clica em uma opção aqui pra eu encaminhar certinho:", "buttons": (
            AUTOMACAO_MENU if state == "automacao_menu" else SITE_MENU if state == "site_menu" else SOCIAL_MENU
        )}

    # ========= BRIEF =========
    if state == "brief":
        if not text:
            return {"type": "text", "text": "Em 1 frase: o que você quer resolver agora?"}

        merge_flow_data(wa_id, {"briefing_text": text})
        set_flow_state(wa_id, "cta")
        return {"type": "buttons", "text": "Agora você prefere:", "buttons": CTA_BTNS}

    # ========= CTA =========
    if state == "cta":
        if cid not in ("CTA_HUMAN", "CTA_PROP"):
            return {"type": "buttons", "text": "Escolhe uma opção pra eu encaminhar:", "buttons": CTA_BTNS}

        merge_flow_data(wa_id, {"cta_choice": cid})
        set_flow_state(wa_id, "name")
        return {"type": "text", "text": "Qual seu nome? (pra eu te encaminhar certo)"}

    # ========= NAME / FINAL =========
    if state == "name":
        if not text:
            return {"type": "text", "text": "Me diz seu nome rapidinho 🙂"}

        merge_flow_data(wa_id, {"lead_name": text})

        final = (get_flow(wa_id) or {}).get("data") or {}

        # salva no CRM
        notes = (
            "NOVO LEAD MUGÔ\n"
            f"Nome: {final.get('lead_name','')}\n"
            f"WhatsApp: {wa_id}\n"
            f"Macro: {final.get('macro','')}\n"
            f"Interesse: {final.get('service_interest','')}\n"
            f"Objetivo: {final.get('briefing_text','')}\n"
            f"CTA: {final.get('cta_choice','')}\n"
        ).strip()

        try:
            set_notes(wa_id, notes)
        except Exception:
            pass

        try:
            set_stage(wa_id, "Qualificado")
        except Exception:
            pass

        # encerra flow
        clear_flow(wa_id)

        # entrega pra IA + contexto (e depois teu app.py faz handoff)
        return {
            "type": "ai",
            "flow_context": final,
            "user_message": (
                "Lead finalizado via botões.\n"
                f"Nome: {final.get('lead_name','')}\n"
                f"Macro: {final.get('macro','')}\n"
                f"Interesse: {final.get('service_interest','')}\n"
                f"Objetivo: {final.get('briefing_text','')}\n"
                f"CTA: {final.get('cta_choice','')}\n"
                "Responda como SDR e encaminhe para humano."
            )
        }

    return None