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

# -------- Automação (3 ok como buttons)
AUTOMACAO_MENU = [
    {"id": "AUTO_ATEND", "title": "Atendimento WhatsApp"},
    {"id": "AUTO_CRM", "title": "CRM / Funil"},
    {"id": "AUTO_FIN", "title": "Financeiro / Cobrança"},
]

# -------- Site / E-commerce (4 -> vira list)
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

# -------- Social / Tráfego (4 -> list)
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

# -------- Vídeos / Avatar com IA (4 -> list)
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

# -------- Consultoria (4 -> list)
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

# -------- Prazo (5 -> list)
PRAZO_BTNS = [
    {"id": "PRAZO_URG", "title": "Urgente (esta semana)"},
    {"id": "PRAZO_7", "title": "Ate 7 dias"},
    {"id": "PRAZO_15", "title": "Ate 15 dias"},
    {"id": "PRAZO_30", "title": "Ate 30 dias"},
    {"id": "PRAZO_PLAN", "title": "Sem pressa (planejar)"},
]

# -------- Investimento (5 -> list)
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

# -------- Origem (5 -> list)
SOURCE_BTNS = [
    {"id": "SRC_IG", "title": "Instagram"},
    {"id": "SRC_INDIC", "title": "Indicacao"},
    {"id": "SRC_GOOGLE", "title": "Google"},
    {"id": "SRC_ANUNCIO", "title": "Anuncio"},
    {"id": "SRC_OUTRO", "title": "Outro"},
]

# -------- CTA final (3 ok como buttons)
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

def _menu_payload(
    *,
    text: str,
    options: List[Dict[str, str]],
    button_text: str = "Selecionar",
    section_title: str = "Opcoes",
) -> Dict[str, Any]:
    """
    WhatsApp Cloud:
      - <=3 opções: interactive buttons
      - >=4 opções: interactive list
    """
    opts = options or []
    if len(opts) <= 3:
        return {"type": "buttons", "text": text, "buttons": opts}

    # vira LIST
    rows = []
    for o in opts:
        rid = (o.get("id") or "").strip()
        ttl = (o.get("title") or "").strip()
        if rid and ttl:
            rows.append({"id": rid, "title": ttl})

    return {
        "type": "list",
        "text": text,
        "button": button_text,
        "sections": [{"title": section_title, "rows": rows}],
    }


# ============================================================
# Flow principal
# ============================================================
def handle_mugo_flow(wa_id: str, user_text: str, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}

    text = (user_text or "").strip()
    cid = (choice_id or "").strip() or text  # comando real (id) ou texto

    # reset
    if text.lower().strip() in ("menu", "inicio", "início"):
        _ensure_main(wa_id)
        return _menu_payload(text="Beleza. Qual e o foco agora?", options=MENU_MAIN, button_text="Escolher", section_title="Servicos")

    # primeiro contato no flow
    if not state:
        _ensure_main(wa_id)
        return _menu_payload(text=_intro_text(), options=MENU_MAIN, button_text="Escolher", section_title="Servicos")

    # ============================================================
    # MAIN
    # ============================================================
    if state == "main":
        if cid == "FLOW_AUTOMATIZAR":
            merge_flow_data(wa_id, {"macro": "automacao"})
            set_flow_state(wa_id, "automacao_menu")
            return _menu_payload(text="O que voce quer automatizar primeiro?", options=AUTOMACAO_MENU, button_text="Escolher", section_title="Automacao")

        if cid == "FLOW_SITE":
            merge_flow_data(wa_id, {"macro": "site"})
            set_flow_state(wa_id, "site_menu")
            return _menu_payload(text="Que tipo de projeto voce quer?", options=SITE_MENU, button_text="Escolher", section_title="Site")

        if cid == "FLOW_SOCIAL":
            merge_flow_data(wa_id, {"macro": "social"})
            set_flow_state(wa_id, "social_menu")
            return _menu_payload(text="O que voce precisa no social?", options=SOCIAL_MENU, button_text="Escolher", section_title="Social")

        if cid == "FLOW_VIDEO_IA":
            merge_flow_data(wa_id, {"macro": "video_ia"})
            set_flow_state(wa_id, "video_menu")
            return _menu_payload(text="Que tipo de video voce quer?", options=VIDEO_MENU, button_text="Escolher", section_title="Videos")

        if cid == "FLOW_CONSULT":
            merge_flow_data(wa_id, {"macro": "consultoria"})
            set_flow_state(wa_id, "consult_menu")
            return _menu_payload(text="Onde voce mais precisa organizar agora?", options=CONSULT_MENU, button_text="Escolher", section_title="Consultoria")

        return _menu_payload(text="Escolhe uma opcao pra eu te guiar:", options=MENU_MAIN, button_text="Escolher", section_title="Servicos")

    # ============================================================
    # AUTOMACAO
    # ============================================================
    if state == "automacao_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    # ============================================================
    # SITE
    # ============================================================
    if state == "site_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SITE_INST":
            set_flow_state(wa_id, "site_inst_goal")
            return _menu_payload(text="Qual objetivo principal do site?", options=SITE_INST_GOAL, button_text="Selecionar", section_title="Objetivo")

        if cid == "SITE_LP":
            set_flow_state(wa_id, "lp_goal")
            return _menu_payload(text="Essa landing e pra que?", options=LP_GOAL, button_text="Selecionar", section_title="Objetivo")

        if cid == "SITE_LOJA":
            set_flow_state(wa_id, "ecom_platform")
            return _menu_payload(text="Onde voce quer vender?", options=ECOM_PLATFORM, button_text="Selecionar", section_title="Plataforma")

        # SITE_MELHORAR
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    if state == "site_inst_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    if state == "lp_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    if state == "ecom_platform":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    # ============================================================
    # SOCIAL
    # ============================================================
    if state == "social_menu":
        merge_flow_data(wa_id, {"service_interest": cid})

        if cid == "SOC_CONT":
            set_flow_state(wa_id, "content_goal")
            return _menu_payload(text="Qual foco do conteudo?", options=CONTENT_GOAL, button_text="Selecionar", section_title="Conteudo")

        if cid == "SOC_GEST":
            set_flow_state(wa_id, "channels_count")
            return _menu_payload(text="Quantas redes voce quer incluir?", options=CHANNELS_COUNT, button_text="Selecionar", section_title="Redes")

        if cid == "SOC_TRAFEGO":
            set_flow_state(wa_id, "ads_goal")
            return _menu_payload(text="Qual objetivo do trafego?", options=ADS_GOAL, button_text="Selecionar", section_title="Trafego")

        if cid == "SOC_AUDIT":
            set_flow_state(wa_id, "audit_goal")
            return _menu_payload(text="Diagnostico de que?", options=AUDIT_GOAL, button_text="Selecionar", section_title="Auditoria")

        return _menu_payload(text="Escolhe uma opcao:", options=SOCIAL_MENU, button_text="Escolher", section_title="Social")

    if state in ("content_goal", "channels_count", "ads_goal", "audit_goal"):
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    # ============================================================
    # VIDEO IA
    # ============================================================
    if state == "video_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "video_goal")
        return _menu_payload(text="Qual objetivo principal do video?", options=VIDEO_GOAL, button_text="Selecionar", section_title="Objetivo")

    if state == "video_goal":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    # ============================================================
    # CONSULTORIA
    # ============================================================
    if state == "consult_menu":
        merge_flow_data(wa_id, {"service_interest": cid})
        set_flow_state(wa_id, "consult_stage")
        return _menu_payload(text="Qual cenario hoje?", options=CONSULT_STAGE, button_text="Selecionar", section_title="Cenario")

    if state == "consult_stage":
        merge_flow_data(wa_id, {"goal": cid})
        set_flow_state(wa_id, "prazo")
        return _menu_payload(text="Qual prazo voce pretende ter?", options=PRAZO_BTNS, button_text="Selecionar", section_title="Prazos")

    # ============================================================
    # PRAZO -> BUDGET -> EMPRESA -> IG -> ORIGEM -> CTA -> FINAL
    # ============================================================
    if state == "prazo":
        merge_flow_data(wa_id, {"prazo": cid})
        final_flow = get_flow(wa_id) or {}
        macro = _pretty((final_flow.get("data") or {}).get("macro") or data.get("macro"))
        set_flow_state(wa_id, "budget")
        return _menu_payload(
            text="Quanto voce tem disponivel para investir?",
            options=_pick_budget_buttons(macro),
            button_text="Selecionar",
            section_title="Investimento",
        )

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
        return _menu_payload(
            text="Como voce conheceu a Mugô?",
            options=SOURCE_BTNS,
            button_text="Selecionar",
            section_title="Origem",
        )

    if state == "source":
        merge_flow_data(wa_id, {"source": cid})
        set_flow_state(wa_id, "cta")
        return _menu_payload(text="Perfeito. Como prefere seguir agora?", options=CTA_BTNS, button_text="Selecionar", section_title="Proximo passo")

    if state == "cta":
        if cid == "CTA_MENU":
            clear_flow(wa_id)
            _ensure_main(wa_id)
            return _menu_payload(text="Show. Qual e o foco agora?", options=MENU_MAIN, button_text="Escolher", section_title="Servicos")

        if cid not in ("CTA_HUMAN", "CTA_PROP"):
            return _menu_payload(text="Escolhe uma opcao pra eu encaminhar certo:", options=CTA_BTNS, button_text="Selecionar", section_title="Proximo passo")

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

        clear_flow(wa_id)

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