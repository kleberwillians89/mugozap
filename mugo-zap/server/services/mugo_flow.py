# mugo-zap/server/services/mugo_flow.py
from typing import Any, Dict, Optional, List

from services.state import (
    get_flow,
    set_flow_state,
    merge_flow_data,
    clear_flow,
    set_notes,
    set_stage,
)

# ============================================================
# MENUS (3 botões sempre)
# ============================================================

MENU_MAIN = [
    {"id": "FLOW_AUTOMATIZAR", "title": "Automação"},
    {"id": "FLOW_SITE", "title": "Site / E-commerce"},
    {"id": "FLOW_SOCIAL", "title": "Social / Tráfego"},
]
MAIN_IDS = {"FLOW_AUTOMATIZAR", "FLOW_SITE", "FLOW_SOCIAL"}

AUTOMACAO_MENU = [
    {"id": "AUTO_ATEND", "title": "Atendimento Whats"},
    {"id": "AUTO_CRM", "title": "CRM / Funil"},
    {"id": "AUTO_FIN", "title": "Financeiro"},
]

SITE_MENU = [
    {"id": "SITE_INST", "title": "Institucional"},
    {"id": "SITE_LP", "title": "Landing page"},
    {"id": "SITE_LOJA", "title": "Loja virtual"},
]

SITE_INST_GOAL = [
    {"id": "SITE_INST_APRESENTAR", "title": "Apresentar"},
    {"id": "SITE_INST_LEADS", "title": "Gerar leads"},
    {"id": "SITE_INST_CRED", "title": "Autoridade"},
]

LP_GOAL = [
    {"id": "LP_LEADS", "title": "Captar leads"},
    {"id": "LP_VENDER", "title": "Vender"},
    {"id": "LP_EVENTO", "title": "Evento"},
]

ECOM_PLATFORM = [
    {"id": "ECOM_SHOPIFY", "title": "Shopify"},
    {"id": "ECOM_NUVEM", "title": "Nuvemshop"},
    {"id": "ECOM_OUTRO", "title": "Outro / Não sei"},
]

SOCIAL_MENU = [
    {"id": "SOC_CONT", "title": "Conteúdo"},
    {"id": "SOC_GEST", "title": "Gestão completa"},
    {"id": "SOC_TRAFEGO", "title": "Tráfego pago"},
]

CONTENT_GOAL = [
    {"id": "CONT_CRESCER", "title": "Crescer"},
    {"id": "CONT_VENDER", "title": "Vender"},
    {"id": "CONT_AUTO", "title": "Autoridade"},
]

CHANNELS_COUNT = [
    {"id": "CH_1", "title": "1 rede"},
    {"id": "CH_2", "title": "2 redes"},
    {"id": "CH_3", "title": "3+ redes"},
]

ADS_GOAL = [
    {"id": "ADS_WHATS", "title": "Leads no Whats"},
    {"id": "ADS_SITE", "title": "Venda no site"},
    {"id": "ADS_REMARK", "title": "Remarketing"},
]

# Prazo paginado (5 -> 2 telas)
PRAZO_P1 = [
    {"id": "PRAZO_URG", "title": "Urgente"},
    {"id": "PRAZO_7", "title": "Até 7 dias"},
    {"id": "PRAZO_MORE", "title": "Mais opções"},
]
PRAZO_P2 = [
    {"id": "PRAZO_15", "title": "Até 15 dias"},
    {"id": "PRAZO_30", "title": "Até 30 dias"},
    {"id": "PRAZO_PLAN", "title": "Sem pressa"},
]

# Budget paginado por macro
BUDGET_AUT_P1 = [
    {"id": "B_AUT_500", "title": "Até R$ 500"},
    {"id": "B_AUT_2000", "title": "R$ 500-2k"},
    {"id": "BUD_MORE", "title": "Mais opções"},
]
BUDGET_AUT_P2 = [
    {"id": "B_AUT_5000", "title": "R$ 2k-5k"},
    {"id": "B_AUT_12000", "title": "R$ 5k+"},
    {"id": "B_AUT_NS", "title": "Ainda não sei"},
]

BUDGET_SITE_P1 = [
    {"id": "B_SITE_2000", "title": "Até R$ 2k"},
    {"id": "B_SITE_5000", "title": "R$ 2k-5k"},
    {"id": "BUD_MORE", "title": "Mais opções"},
]
BUDGET_SITE_P2 = [
    {"id": "B_SITE_12000", "title": "R$ 5k-12k"},
    {"id": "B_SITE_25000", "title": "R$ 12k+"},
    {"id": "B_SITE_NS", "title": "Ainda não sei"},
]

BUDGET_SOC_P1 = [
    {"id": "B_SOC_800", "title": "Até R$ 800"},
    {"id": "B_SOC_2000", "title": "R$ 800-2k"},
    {"id": "BUD_MORE", "title": "Mais opções"},
]
BUDGET_SOC_P2 = [
    {"id": "B_SOC_5000", "title": "R$ 2k-5k"},
    {"id": "B_SOC_5000P", "title": "R$ 5k+"},
    {"id": "B_SOC_NS", "title": "Ainda não sei"},
]

SRC_P1 = [
    {"id": "SRC_IG", "title": "Instagram"},
    {"id": "SRC_INDIC", "title": "Indicação"},
    {"id": "SRC_MORE", "title": "Mais opções"},
]
SRC_P2 = [
    {"id": "SRC_GOOGLE", "title": "Google"},
    {"id": "SRC_ANUNCIO", "title": "Anúncio"},
    {"id": "SRC_OUTRO", "title": "Outro"},
]

CTA_BTNS = [
    {"id": "CTA_HUMAN", "title": "Falar com Julia"},
    {"id": "CTA_PROP", "title": "Receber proposta"},
    {"id": "CTA_MENU", "title": "Menu"},
]


# ============================================================
# Helpers
# ============================================================
def _intro_text() -> str:
    return (
        "Oi! Aqui é da Mugô.\n"
        "A gente destrava operação com automação, sites e performance.\n"
        "Qual é o foco agora?"
    )

def _pretty(v: Any) -> str:
    return (str(v) if v is not None else "").strip()

def _ensure_main(wa_id: str):
    set_flow_state(wa_id, "main")

def _budget_pages(macro: str):
    m = (macro or "").lower()
    if m == "automacao":
        return BUDGET_AUT_P1, BUDGET_AUT_P2
    if m == "site":
        return BUDGET_SITE_P1, BUDGET_SITE_P2
    return BUDGET_SOC_P1, BUDGET_SOC_P2


# ============================================================
# Flow
# ============================================================
def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    text = (user_text or "").strip()
    lower = text.lower().strip()

    # reset simples (menu/inicio)
    if lower in ("menu", "inicio", "início"):
        _ensure_main(wa_id)
        return {"type": "buttons", "text": "Beleza. Qual é o foco agora?", "buttons": MENU_MAIN}

    # ✅ CORREÇÃO CRÍTICA:
    # Se state está vazio, mas já veio um comando FLOW_* (clique do botão),
    # a gente seta main e continua o roteamento (não cai na IA).
    if not state:
        if (choice_id or text).strip() in MAIN_IDS:
            state = "main"
            _ensure_main(wa_id)
        else:
            _ensure_main(wa_id)
            return {"type": "buttons", "text": _intro_text(), "buttons": MENU_MAIN}

    cid = (choice_id or "").strip() or text

    # ============================================================
    # MAIN
    # ============================================================
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

    # ============================================================
    # AUTOMACAO
    # ============================================================
    if state == "automacao_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "prazo_p1")
        return {"type": "buttons", "text": "Qual prazo você pretende ter?", "buttons": PRAZO_P1}

    # ============================================================
    # SITE
    # ============================================================
    if state == "site_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SITE_INST":
            set_flow_state(wa_id, "site_inst_goal")
            return {"type": "buttons", "text": "Qual objetivo do site?", "buttons": SITE_INST_GOAL}

        if cid == "SITE_LP":
            set_flow_state(wa_id, "lp_goal")
            return {"type": "buttons", "text": "Essa landing é pra quê?", "buttons": LP_GOAL}

        if cid == "SITE_LOJA":
            set_flow_state(wa_id, "ecom_platform")
            return {"type": "buttons", "text": "Onde você quer vender?", "buttons": ECOM_PLATFORM}

        return {"type": "buttons", "text": "Escolhe uma opção:", "buttons": SITE_MENU}

    if state in ("site_inst_goal", "lp_goal", "ecom_platform"):
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo_p1")
        return {"type": "buttons", "text": "Qual prazo você pretende ter?", "buttons": PRAZO_P1}

    # ============================================================
    # SOCIAL
    # ============================================================
    if state == "social_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SOC_CONT":
            set_flow_state(wa_id, "content_goal")
            return {"type": "buttons", "text": "Qual foco do conteúdo?", "buttons": CONTENT_GOAL}

        if cid == "SOC_GEST":
            set_flow_state(wa_id, "channels_count")
            return {"type": "buttons", "text": "Quantas redes você quer incluir?", "buttons": CHANNELS_COUNT}

        if cid == "SOC_TRAFEGO":
            set_flow_state(wa_id, "ads_goal")
            return {"type": "buttons", "text": "Qual objetivo do tráfego?", "buttons": ADS_GOAL}

        return {"type": "buttons", "text": "Escolhe uma opção:", "buttons": SOCIAL_MENU}

    if state in ("content_goal", "channels_count", "ads_goal"):
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo_p1")
        return {"type": "buttons", "text": "Qual prazo você pretende ter?", "buttons": PRAZO_P1}

    # ============================================================
    # PRAZO (paginado)
    # ============================================================
    if state == "prazo_p1":
        if cid == "PRAZO_MORE":
            set_flow_state(wa_id, "prazo_p2")
            return {"type": "buttons", "text": "Qual prazo você pretende ter?", "buttons": PRAZO_P2}

        merge_flow_data(wa_id, {"prazo": cid})
        set_flow_state(wa_id, "budget_p1")
        macro = _pretty((get_flow(wa_id) or {}).get("data", {}).get("macro"))
        b1, _ = _budget_pages(macro)
        return {"type": "buttons", "text": "Quanto você tem disponível para investir?", "buttons": b1}

    if state == "prazo_p2":
        merge_flow_data(wa_id, {"prazo": cid})
        set_flow_state(wa_id, "budget_p1")
        macro = _pretty((get_flow(wa_id) or {}).get("data", {}).get("macro"))
        b1, _ = _budget_pages(macro)
        return {"type": "buttons", "text": "Quanto você tem disponível para investir?", "buttons": b1}

    # ============================================================
    # BUDGET (paginado)
    # ============================================================
    if state == "budget_p1":
        if cid == "BUD_MORE":
            set_flow_state(wa_id, "budget_p2")
            macro = _pretty((get_flow(wa_id) or {}).get("data", {}).get("macro"))
            _, b2 = _budget_pages(macro)
            return {"type": "buttons", "text": "Quanto você tem disponível para investir?", "buttons": b2}

        merge_flow_data(wa_id, {"budget_range": cid})
        set_flow_state(wa_id, "company_name")
        return {"type": "text", "text": "Qual o nome da empresa?"}

    if state == "budget_p2":
        merge_flow_data(wa_id, {"budget_range": cid})
        set_flow_state(wa_id, "company_name")
        return {"type": "text", "text": "Qual o nome da empresa?"}

    # ============================================================
    # EMPRESA / IG / ORIGEM / CTA
    # ============================================================
    if state == "company_name":
        if not text:
            return {"type": "text", "text": "Qual o nome da empresa?"}
        merge_flow_data(wa_id, {"company_name": text})
        set_flow_state(wa_id, "instagram")
        return {"type": "text", "text": "Me manda o link do Instagram (ou @user). Se não tiver, digita: nao tenho"}

    if state == "instagram":
        if not text:
            return {"type": "text", "text": "Me manda o link do Instagram (ou @user). Se não tiver, digita: nao tenho"}
        merge_flow_data(wa_id, {"instagram": text})
        set_flow_state(wa_id, "source_p1")
        return {"type": "buttons", "text": "Como você conheceu a Mugô?", "buttons": SRC_P1}

    if state == "source_p1":
        if cid == "SRC_MORE":
            set_flow_state(wa_id, "source_p2")
            return {"type": "buttons", "text": "Como você conheceu a Mugô?", "buttons": SRC_P2}

        merge_flow_data(wa_id, {"source": cid})
        set_flow_state(wa_id, "cta")
        return {"type": "buttons", "text": "Perfeito. Como prefere seguir agora?", "buttons": CTA_BTNS}

    if state == "source_p2":
        merge_flow_data(wa_id, {"source": cid})
        set_flow_state(wa_id, "cta")
        return {"type": "buttons", "text": "Perfeito. Como prefere seguir agora?", "buttons": CTA_BTNS}

    if state == "cta":
        if cid == "CTA_MENU":
            clear_flow(wa_id)
            _ensure_main(wa_id)
            return {"type": "buttons", "text": "Show. Qual é o foco agora?", "buttons": MENU_MAIN}

        if cid not in ("CTA_HUMAN", "CTA_PROP"):
            return {"type": "buttons", "text": "Escolhe uma opção:", "buttons": CTA_BTNS}

        merge_flow_data(wa_id, {"cta_choice": cid})
        final = (get_flow(wa_id) or {}).get("data") or {}

        notes = (
            "NOVO LEAD (Mini-Briefing Mugô)\n"
            f"WhatsApp: {wa_id}\n"
            f"Macro: {final.get('macro')}\n"
            f"Serviço: {final.get('service_interest')}\n"
            f"Objetivo: {final.get('goal')}\n"
            f"Prazo: {final.get('prazo')}\n"
            f"Investimento: {final.get('budget_range')}\n"
            f"Empresa: {final.get('company_name')}\n"
            f"Instagram: {final.get('instagram')}\n"
            f"Origem: {final.get('source')}\n"
            f"CTA: {final.get('cta_choice')}\n"
        ).strip()

        try:
            set_notes(wa_id, notes)
        except Exception:
            pass

        try:
            set_stage(wa_id, "Qualificado")
        except Exception:
            pass

        clear_flow(wa_id)

        return {
            "type": "ai",
            "flow_context": final,
            "user_message": (
                "Lead finalizado via mini-briefing.\n"
                f"Empresa: {final.get('company_name')}\n"
                f"Macro: {final.get('macro')}\n"
                f"Serviço: {final.get('service_interest')}\n"
                f"Objetivo: {final.get('goal')}\n"
                f"Prazo: {final.get('prazo')}\n"
                f"Investimento: {final.get('budget_range')}\n"
                f"Instagram: {final.get('instagram')}\n"
                f"Origem: {final.get('source')}\n"
                f"CTA: {final.get('cta_choice')}\n"
                "Responda curto, confirme entendimento e encaminhe para especialista."
            ),
        }

    return None