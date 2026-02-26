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
# MENUS (sem emoji no title pra evitar falha do WhatsApp)
# ============================================================
MENU_MAIN: List[Dict[str, str]] = [
    {"id": "FLOW_AUTOMATIZAR", "title": "Automação"},
    {"id": "FLOW_SITE", "title": "Site / E-commerce"},
    {"id": "FLOW_SOCIAL", "title": "Social / Tráfego"},
    {"id": "FLOW_VIDEO_IA", "title": "Vídeos / Avatar com IA"},
    {"id": "FLOW_CONSULT", "title": "Consultoria Mugô"},
]

# -------- Automação
AUTOMACAO_MENU = [
    {"id": "AUTO_ATEND", "title": "Atendimento WhatsApp"},
    {"id": "AUTO_CRM", "title": "CRM / Funil"},
    {"id": "AUTO_FIN", "title": "Financeiro / Cobrança"},
]

# -------- Site / E-commerce
SITE_MENU = [
    {"id": "SITE_INST", "title": "Institucional"},
    {"id": "SITE_LP", "title": "Landing page"},
    {"id": "SITE_LOJA", "title": "Loja virtual"},
    {"id": "SITE_MELHORAR", "title": "Ja tenho site (melhorar)"},
]

SITE_INST_GOAL = [
    {"id": "SITE_INST_APRESENTAR", "title": "Apresentar a empresa"},
    {"id": "SITE_INST_WHATS", "title": "Gerar leads no Whats"},
    {"id": "SITE_INST_PORTF", "title": "Portfolio / cases"},
    {"id": "SITE_INST_CRED", "title": "Credibilidade / autoridade"},
]

LP_GOAL = [
    {"id": "LP_LEADS", "title": "Captar leads"},
    {"id": "LP_VENDER", "title": "Vender um produto"},
    {"id": "LP_EVENTO", "title": "Evento / lancamento"},
    {"id": "LP_ESPERA", "title": "Lista de espera"},
]

ECOM_PLATFORM = [
    {"id": "ECOM_SHOPIFY", "title": "Shopify"},
    {"id": "ECOM_NUVEM", "title": "Nuvemshop"},
    {"id": "ECOM_WOO", "title": "WooCommerce"},
    {"id": "ECOM_NAO_SEI", "title": "Nao sei (me orienta)"},
]

# -------- Social / Tráfego
SOCIAL_MENU = [
    {"id": "SOC_CONT", "title": "Conteudo"},
    {"id": "SOC_GEST", "title": "Gestao completa"},
    {"id": "SOC_TRAFEGO", "title": "Trafego pago"},
    {"id": "SOC_AUDIT", "title": "Diagnostico (auditoria)"},
]

CONTENT_GOAL = [
    {"id": "CONT_CRESCER", "title": "Crescer seguidores"},
    {"id": "CONT_VENDER", "title": "Vender (conversao)"},
    {"id": "CONT_AUTO", "title": "Autoridade"},
    {"id": "CONT_ENG", "title": "Comunidade / engajar"},
]

CHANNELS_COUNT = [
    {"id": "CH_1", "title": "1 rede"},
    {"id": "CH_2", "title": "2 redes"},
    {"id": "CH_3", "title": "3+ redes"},
    {"id": "CH_NS", "title": "Nao sei"},
]

ADS_GOAL = [
    {"id": "ADS_WHATS", "title": "Leads no Whats"},
    {"id": "ADS_SITE", "title": "Venda no site"},
    {"id": "ADS_IG", "title": "Mensagens no Instagram"},
    {"id": "ADS_REMARK", "title": "Remarketing"},
]

AUDIT_GOAL = [
    {"id": "AUD_CONT", "title": "Conteudo"},
    {"id": "AUD_PERFIL", "title": "Perfil / posicionamento"},
    {"id": "AUD_FUNIL", "title": "Funil / conversao"},
    {"id": "AUD_TRAFEGO", "title": "Trafego"},
]

# -------- Vídeos / Avatar com IA
VIDEO_MENU = [
    {"id": "VID_INST", "title": "Institucional (marca/empresa)"},
    {"id": "VID_REELS", "title": "Reels (conteudo)"},
    {"id": "VID_AVATAR", "title": "Avatar apresentador"},
    {"id": "VID_PROD", "title": "Produto (ads/venda)"},
]

VIDEO_GOAL = [
    {"id": "VID_GOAL_AUTO", "title": "Autoridade"},
    {"id": "VID_GOAL_VENDER", "title": "Vendas / conversao"},
    {"id": "VID_GOAL_EXPL", "title": "Explicar servico"},
    {"id": "VID_GOAL_APRES", "title": "Apresentar produto"},
]

# -------- Consultoria
CONSULT_MENU = [
    {"id": "CONS_MKT", "title": "Marketing e vendas"},
    {"id": "CONS_PROC", "title": "Processos / operacao"},
    {"id": "CONS_AUTO", "title": "Automacao geral"},
    {"id": "CONS_FULL", "title": "Estrutura completa"},
]

CONSULT_STAGE = [
    {"id": "CONS_S0", "title": "Comecando do zero"},
    {"id": "CONS_S1", "title": "Vendo, mas baguncado"},
    {"id": "CONS_S2", "title": "Tenho equipe, falta processo"},
    {"id": "CONS_S3", "title": "Quero escalar"},
]

# -------- Prazo (universal)
PRAZO_BTNS = [
    {"id": "PRAZO_URG", "title": "Urgente (esta semana)"},
    {"id": "PRAZO_7", "title": "Ate 7 dias"},
    {"id": "PRAZO_15", "title": "Ate 15 dias"},
    {"id": "PRAZO_30", "title": "Ate 30 dias"},
    {"id": "PRAZO_PLAN", "title": "Sem pressa (planejar)"},
]

# -------- Investimento (por macro)
BUDGET_AUTOMACAO = [
    {"id": "B_AUT_500", "title": "Ate R$ 500"},
    {"id": "B_AUT_2000", "title": "R$ 500 a R$ 2.000"},
    {"id": "B_AUT_5000", "title": "R$ 2.000 a R$ 5.000"},
    {"id": "B_AUT_12000", "title": "R$ 5.000 a R$ 12.000+"},
    {"id": "B_AUT_NS", "title": "Ainda nao sei"},
]

BUDGET_SITE = [
    {"id": "B_SITE_2000", "title": "Ate R$ 2.000"},
    {"id": "B_SITE_5000", "title": "R$ 2.000 a R$ 5.000"},
    {"id": "B_SITE_12000", "title": "R$ 5.000 a R$ 12.000"},
    {"id": "B_SITE_25000", "title": "R$ 12.000 a R$ 25.000+"},
    {"id": "B_SITE_NS", "title": "Ainda nao sei"},
]

BUDGET_SOCIAL = [
    {"id": "B_SOC_800", "title": "Ate R$ 800/mes"},
    {"id": "B_SOC_2000", "title": "R$ 800 a R$ 2.000/mes"},
    {"id": "B_SOC_5000", "title": "R$ 2.000 a R$ 5.000/mes"},
    {"id": "B_SOC_5000P", "title": "R$ 5.000+/mes"},
    {"id": "B_SOC_NS", "title": "Ainda nao sei"},
]

BUDGET_VIDEO = [
    {"id": "B_VID_500", "title": "Ate R$ 500"},
    {"id": "B_VID_1500", "title": "R$ 500 a R$ 1.500"},
    {"id": "B_VID_4000", "title": "R$ 1.500 a R$ 4.000"},
    {"id": "B_VID_4000P", "title": "R$ 4.000+"},
    {"id": "B_VID_NS", "title": "Ainda nao sei"},
]

BUDGET_CONSULT = [
    {"id": "B_CONS_1000", "title": "Ate R$ 1.000"},
    {"id": "B_CONS_3000", "title": "R$ 1.000 a R$ 3.000"},
    {"id": "B_CONS_8000", "title": "R$ 3.000 a R$ 8.000"},
    {"id": "B_CONS_8000P", "title": "R$ 8.000+"},
    {"id": "B_CONS_NS", "title": "Ainda nao sei"},
]

# -------- Origem
SOURCE_BTNS = [
    {"id": "SRC_IG", "title": "Instagram"},
    {"id": "SRC_INDIC", "title": "Indicacao"},
    {"id": "SRC_GOOGLE", "title": "Google"},
    {"id": "SRC_ANUNCIO", "title": "Anuncio"},
    {"id": "SRC_OUTRO", "title": "Outro"},
]

# -------- CTA final
CTA_BTNS = [
    {"id": "CTA_HUMAN", "title": "Falar com Julia agora"},
    {"id": "CTA_PROP", "title": "Receber proposta"},
    {"id": "CTA_MENU", "title": "Voltar ao menu"},
]


# ============================================================
# Helpers internos
# ============================================================
def _intro_text() -> str:
    return (
        "Oi! Aqui e da Mugô.\n"
        "A gente destrava operacao com automacao, IA, sites e performance.\n"
        "Qual e o foco agora?"
    )

def _pick_budget_buttons(macro: str) -> List[Dict[str, str]]:
    m = (macro or "").lower()
    if m == "automacao":
        return BUDGET_AUTOMACAO
    if m == "site":
        return BUDGET_SITE
    if m == "social":
        return BUDGET_SOCIAL
    if m == "video_ia":
        return BUDGET_VIDEO
    if m == "consultoria":
        return BUDGET_CONSULT
    return BUDGET_AUTOMACAO

def _pretty(v: Any) -> str:
    return (str(v) if v is not None else "").strip()

def _ensure_main(wa_id: str):
    set_flow_state(wa_id, "main")


# ============================================================
# Flow principal
# ============================================================
def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}

    text = (user_text or "").strip()
    cid = (choice_id or "").strip() or text

    # reset
    if text.lower().strip() in ("menu", "inicio", "início"):
        _ensure_main(wa_id)
        return {"type": "buttons", "text": "Beleza. Qual e o foco agora?", "buttons": MENU_MAIN}

    # primeiro contato no flow
    if not state:
        _ensure_main(wa_id)
        return {"type": "buttons", "text": _intro_text(), "buttons": MENU_MAIN}

    # ============================================================
    # MAIN
    # ============================================================
    if state == "main":
        if cid == "FLOW_AUTOMATIZAR":
            merge_flow_data(wa_id, {"macro": "automacao"})
            set_flow_state(wa_id, "automacao_menu")
            return {"type": "buttons", "text": "O que voce quer automatizar primeiro?", "buttons": AUTOMACAO_MENU}

        if cid == "FLOW_SITE":
            merge_flow_data(wa_id, {"macro": "site"})
            set_flow_state(wa_id, "site_menu")
            return {"type": "buttons", "text": "Que tipo de projeto voce quer?", "buttons": SITE_MENU}

        if cid == "FLOW_SOCIAL":
            merge_flow_data(wa_id, {"macro": "social"})
            set_flow_state(wa_id, "social_menu")
            return {"type": "buttons", "text": "O que voce precisa no social?", "buttons": SOCIAL_MENU}

        if cid == "FLOW_VIDEO_IA":
            merge_flow_data(wa_id, {"macro": "video_ia"})
            set_flow_state(wa_id, "video_menu")
            return {"type": "buttons", "text": "Que tipo de video voce quer?", "buttons": VIDEO_MENU}

        if cid == "FLOW_CONSULT":
            merge_flow_data(wa_id, {"macro": "consultoria"})
            set_flow_state(wa_id, "consult_menu")
            return {"type": "buttons", "text": "Onde voce mais precisa organizar agora?", "buttons": CONSULT_MENU}

        return {"type": "buttons", "text": "Escolhe uma opcao pra eu te guiar:", "buttons": MENU_MAIN}

    # ============================================================
    # AUTOMACAO
    # ============================================================
    if state == "automacao_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    # ============================================================
    # SITE
    # ============================================================
    if state == "site_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SITE_INST":
            set_flow_state(wa_id, "site_inst_goal")
            return {"type": "buttons", "text": "Qual objetivo principal do site?", "buttons": SITE_INST_GOAL}

        if cid == "SITE_LP":
            set_flow_state(wa_id, "lp_goal")
            return {"type": "buttons", "text": "Essa landing e pra que?", "buttons": LP_GOAL}

        if cid == "SITE_LOJA":
            set_flow_state(wa_id, "ecom_platform")
            return {"type": "buttons", "text": "Onde voce quer vender?", "buttons": ECOM_PLATFORM}

        # SITE_MELHORAR
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    if state == "site_inst_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    if state == "lp_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    if state == "ecom_platform":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    # ============================================================
    # SOCIAL
    # ============================================================
    if state == "social_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SOC_CONT":
            set_flow_state(wa_id, "content_goal")
            return {"type": "buttons", "text": "Qual foco do conteudo?", "buttons": CONTENT_GOAL}

        if cid == "SOC_GEST":
            set_flow_state(wa_id, "channels_count")
            return {"type": "buttons", "text": "Quantas redes voce quer incluir?", "buttons": CHANNELS_COUNT}

        if cid == "SOC_TRAFEGO":
            set_flow_state(wa_id, "ads_goal")
            return {"type": "buttons", "text": "Qual objetivo do trafego?", "buttons": ADS_GOAL}

        if cid == "SOC_AUDIT":
            set_flow_state(wa_id, "audit_goal")
            return {"type": "buttons", "text": "Diagnostico de que?", "buttons": AUDIT_GOAL}

        return {"type": "buttons", "text": "Escolhe uma opcao:", "buttons": SOCIAL_MENU}

    if state in ("content_goal", "channels_count", "ads_goal", "audit_goal"):
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    # ============================================================
    # VIDEO IA
    # ============================================================
    if state == "video_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "video_goal")
        return {"type": "buttons", "text": "Qual objetivo principal do video?", "buttons": VIDEO_GOAL}

    if state == "video_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    # ============================================================
    # CONSULTORIA
    # ============================================================
    if state == "consult_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "consult_stage")
        return {"type": "buttons", "text": "Qual cenario hoje?", "buttons": CONSULT_STAGE}

    if state == "consult_stage":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return {"type": "buttons", "text": "Qual prazo voce pretende ter?", "buttons": PRAZO_BTNS}

    # ============================================================
    # PRAZO -> BUDGET -> EMPRESA -> IG -> ORIGEM -> CTA -> FINAL
    # ============================================================
    if state == "prazo":
        merge_flow_data(wa_id, {"prazo": cid})
        macro = _pretty((get_flow(wa_id) or {}).get("data", {}).get("macro") if isinstance(get_flow(wa_id), dict) else data.get("macro"))
        set_flow_state(wa_id, "budget")
        return {"type": "buttons", "text": "Quanto voce tem disponivel para investir?", "buttons": _pick_budget_buttons(macro)}

    if state == "budget":
        merge_flow_data(wa_id, {"budget_range": cid})
        set_flow_state(wa_id, "company_name")
        return {"type": "text", "text": "Qual o nome da empresa?"}

    if state == "company_name":
        if not text:
            return {"type": "text", "text": "Qual o nome da empresa?"}
        merge_flow_data(wa_id, {"company_name": text})
        set_flow_state(wa_id, "instagram")
        return {"type": "text", "text": "Me manda o link do Instagram (ou @user). Se nao tiver, digita: nao tenho"}

    if state == "instagram":
        if not text:
            return {"type": "text", "text": "Me manda o link do Instagram (ou @user). Se nao tiver, digita: nao tenho"}
        merge_flow_data(wa_id, {"instagram": text})
        set_flow_state(wa_id, "source")
        return {"type": "buttons", "text": "Como voce conheceu a Mugô?", "buttons": SOURCE_BTNS}

    if state == "source":
        merge_flow_data(wa_id, {"source": cid})
        set_flow_state(wa_id, "cta")
        return {"type": "buttons", "text": "Perfeito. Como prefere seguir agora?", "buttons": CTA_BTNS}

    if state == "cta":
        if cid == "CTA_MENU":
            clear_flow(wa_id)
            _ensure_main(wa_id)
            return {"type": "buttons", "text": "Show. Qual e o foco agora?", "buttons": MENU_MAIN}

        if cid not in ("CTA_HUMAN", "CTA_PROP"):
            return {"type": "buttons", "text": "Escolhe uma opcao pra eu encaminhar certo:", "buttons": CTA_BTNS}

        merge_flow_data(wa_id, {"cta_choice": cid})

        final = (get_flow(wa_id) or {}).get("data") or {}
        macro = _pretty(final.get("macro"))
        service_interest = _pretty(final.get("service_interest"))
        goal = _pretty(final.get("goal"))
        prazo = _pretty(final.get("prazo"))
        budget_range = _pretty(final.get("budget_range"))
        company_name = _pretty(final.get("company_name"))
        instagram = _pretty(final.get("instagram"))
        source = _pretty(final.get("source"))
        cta_choice = _pretty(final.get("cta_choice"))

        notes = (
            "NOVO LEAD (Mini-Briefing Mugô)\n"
            f"WhatsApp: {wa_id}\n"
            f"Macro: {macro}\n"
            f"Servico: {service_interest}\n"
            f"Subtipo/Objetivo: {goal}\n"
            f"Prazo: {prazo}\n"
            f"Investimento: {budget_range}\n"
            f"Empresa: {company_name}\n"
            f"Instagram: {instagram}\n"
            f"Origem: {source}\n"
            f"CTA: {cta_choice}\n"
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

        # Entrega para IA com contexto (pra responder curto e já encaminhar)
        return {
            "type": "ai",
            "flow_context": final,
            "user_message": (
                "Lead finalizado via mini-briefing.\n"
                f"Empresa: {company_name}\n"
                f"Macro: {macro}\n"
                f"Servico: {service_interest}\n"
                f"Objetivo: {goal}\n"
                f"Prazo: {prazo}\n"
                f"Investimento: {budget_range}\n"
                f"Instagram: {instagram}\n"
                f"Origem: {source}\n"
                f"CTA: {cta_choice}\n"
                "Responda curto, confirme entendimento e encaminhe para especialista."
            ),
        }

    return None