# mugo-zap/server/services/mugo_flow.py
from typing import Any, Dict, Optional

from services.state import (
    get_flow,
    set_flow_state,
    merge_flow_data,
    clear_flow,
    set_notes,
    set_handoff_pending,
    set_handoff_topic,
    set_stage,
)

# IDs estáveis (use ID do botão, não o "title")
MENU_A = [
    {"id": "mugo_automation", "title": "Automatizar processos"},
    {"id": "mugo_site", "title": "Criar site / e-commerce"},
    {"id": "mugo_more", "title": "Mais opções"},
]

MENU_B = [
    {"id": "mugo_social", "title": "Social Media"},
    {"id": "mugo_video", "title": "Vídeos / Avatar IA"},
    {"id": "mugo_consult", "title": "Consultoria completa"},
]

CTA_BTNS = [
    {"id": "cta_human", "title": "Falar com especialista"},
    {"id": "cta_proposal", "title": "Receber proposta"},
]

def _choice(choice_id: str, fallback_text: str) -> str:
    c = (choice_id or "").strip()
    return c if c else (fallback_text or "").strip()

def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    """
    Retorna dict no formato:
      {"type":"text","text":"..."}  ou
      {"type":"buttons","text":"...","buttons":[{id,title},...]}
    ou None para cair no fluxo normal (IA).
    """
    flow = get_flow(wa_id)
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}
    text = (user_text or "").strip()
    cid = _choice(choice_id, text)

    # Se usuário digitar "menu", reinicia funil
    if text.lower().strip() in ("menu", "inicio", "início"):
        set_flow_state(wa_id, "mugo_menu_a")
        return {"type": "buttons", "text": "Como você quer trabalhar com a Mugô hoje?", "buttons": MENU_A}

    # INÍCIO: se não tem estado, começa pelo menu
    if not state:
        set_flow_state(wa_id, "mugo_menu_a")
        return {"type": "buttons", "text": "Como você quer trabalhar com a Mugô hoje?", "buttons": MENU_A}

    # MENU A
    if state == "mugo_menu_a":
        if cid == "mugo_more":
            set_flow_state(wa_id, "mugo_menu_b")
            return {"type": "buttons", "text": "Perfeito. Escolhe uma opção:", "buttons": MENU_B}

        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "mugo_brief")
        return {"type": "text", "text": "Em uma frase, o que você quer resolver agora?"}

    # MENU B
    if state == "mugo_menu_b":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "mugo_brief")
        return {"type": "text", "text": "Em uma frase, o que você quer resolver agora?"}

    # BRIEF
    if state == "mugo_brief":
        if not text:
            return {"type": "text", "text": "Me diz em uma frase o que você quer resolver agora."}

        merge_flow_data(wa_id, {"briefing_text": text})
        set_flow_state(wa_id, "mugo_cta")
        return {"type": "buttons", "text": "Agora você prefere:", "buttons": CTA_BTNS}

    # CTA
    if state == "mugo_cta":
        if cid not in ("cta_human", "cta_proposal"):
            return {"type": "buttons", "text": "Escolhe uma opção pra eu te encaminhar certo:", "buttons": CTA_BTNS}

        merge_flow_data(wa_id, {"cta_choice": cid})
        set_flow_state(wa_id, "mugo_name")
        return {"type": "text", "text": "Antes de eu encaminhar, qual seu nome?"}

    # NAME + FINALIZA
    if state == "mugo_name":
        if not text:
            return {"type": "text", "text": "Qual seu nome? (só pra eu encaminhar certinho)"}

        merge_flow_data(wa_id, {"lead_name": text})
        final = get_flow(wa_id).get("data") or {}

        service = final.get("service_interest") or ""
        briefing = final.get("briefing_text") or ""
        cta = final.get("cta_choice") or ""
        lead_name = final.get("lead_name") or ""

        cta_label = "Falar com especialista" if cta == "cta_human" else "Receber proposta"

        notes = (
            "NOVO LEAD MUGÔ\n"
            f"Nome: {lead_name}\n"
            f"WhatsApp: {wa_id}\n"
            f"Serviço: {service}\n"
            f"Objetivo: {briefing}\n"
            f"CTA: {cta_label}\n"
        ).strip()

        # Salva e aciona handoff
        try:
            set_notes(wa_id, notes)
        except Exception:
            pass
        try:
            set_stage(wa_id, "Qualificado")
        except Exception:
            pass

        try:
            set_handoff_pending(wa_id, False)
            set_handoff_topic(wa_id, "Novo Lead Mugô")
        except Exception:
            pass

        clear_flow(wa_id)

        return {"type": "text", "text": f"Perfeito, {lead_name}. Estou encaminhando seu pedido para o nosso time agora."}

    return None