# mugo-zap/server/services/mugo_flow.py
from typing import Any, Dict, Optional

from services.state import (
    get_flow,
    set_flow_state,
    merge_flow_data,
    clear_flow,
    set_notes,
    set_stage,
)

MENU_MAIN = [
    {"id": "FLOW_AUTOMATIZAR", "title": "⚙️ Automação"},
    {"id": "FLOW_SITE", "title": "🌐 Site / E-commerce"},
    {"id": "FLOW_SOCIAL", "title": "📈 Social / Tráfego"},
]

AUTOMACAO_MENU = [
    {"id": "AUTO_ATEND", "title": "💬 Atendimento WhatsApp"},
    {"id": "AUTO_CRM", "title": "📌 CRM / Funil"},
    {"id": "AUTO_FIN", "title": "💳 Financeiro / Cobrança"},
]

SITE_MENU = [
    {"id": "SITE_INST", "title": "🏢 Institucional"},
    {"id": "SITE_LP", "title": "🎯 Landing page"},
    {"id": "SITE_LOJA", "title": "🛒 Loja virtual"},
]

SOCIAL_MENU = [
    {"id": "SOC_CONT", "title": "✍️ Conteúdo"},
    {"id": "SOC_GEST", "title": "🧠 Gestão completa"},
    {"id": "SOC_TRAFEGO", "title": "📣 Tráfego pago"},
]

CTA_BTNS = [
    {"id": "CTA_HUMAN", "title": "🤝 Falar com especialista"},
    {"id": "CTA_PROP", "title": "📩 Receber proposta"},
]

def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}

    text = (user_text or "").strip()
    cid = (choice_id or "").strip() or text

    # reset
    if text.lower().strip() in ("menu", "inicio", "início"):
        set_flow_state(wa_id, "main")
        return {"type": "buttons", "text": "Beleza. Qual é o foco agora?", "buttons": MENU_MAIN}

    if not state:
        set_flow_state(wa_id, "main")
        return {"type": "buttons", "text": "Oi. Aqui é da Mugô. O que você quer destravar agora?", "buttons": MENU_MAIN}

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

    if state in ("automacao_menu", "site_menu", "social_menu"):
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "brief")
        return {"type": "text", "text": "Em uma frase, o que você quer resolver agora?"}

    if state == "brief":
        if not text:
            return {"type": "text", "text": "Me diz em uma frase o que você quer resolver agora."}

        merge_flow_data(wa_id, {"briefing_text": text})
        set_flow_state(wa_id, "cta")
        return {"type": "buttons", "text": "Agora você prefere:", "buttons": CTA_BTNS}

    if state == "cta":
        if cid not in ("CTA_HUMAN", "CTA_PROP"):
            return {"type": "buttons", "text": "Escolhe uma opção pra eu encaminhar certo:", "buttons": CTA_BTNS}

        merge_flow_data(wa_id, {"cta_choice": cid})
        set_flow_state(wa_id, "name")
        return {"type": "text", "text": "Antes de eu encaminhar, qual seu nome?"}

    if state == "name":
        if not text:
            return {"type": "text", "text": "Qual seu nome? (só pra eu encaminhar certinho)"}

        merge_flow_data(wa_id, {"lead_name": text})
        final = (get_flow(wa_id) or {}).get("data") or {}

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

        # ✅ aqui NÃO envia msg — entrega pra IA com contexto
        return {
            "type": "ai",
            "flow_context": final,
            "user_message": (
                f"Lead finalizado via botões.\n"
                f"Nome: {final.get('lead_name','')}\n"
                f"Interesse: {final.get('service_interest','')}\n"
                f"Objetivo: {final.get('briefing_text','')}\n"
                f"CTA: {final.get('cta_choice','')}\n"
                "Agora responda como SDR e encaminhe."
            )
        }

    return None