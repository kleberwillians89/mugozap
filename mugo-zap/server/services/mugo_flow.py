# mugo-zap/server/services/mugo_flow.py
from __future__ import annotations

from typing import Any, Dict, Optional

from services.state import get_flow, merge_flow_data, set_flow_state, clear_flow


# =========================
# Helpers de UI
# =========================
def _btn(text: str, buttons: list[dict]) -> Dict[str, Any]:
    return {"type": "buttons", "text": text, "buttons": buttons}


def _text(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}


def _norm(s: str) -> str:
    return (s or "").strip()


# =========================
# IDs (STEP 1)
# =========================
BTN_AUTOMACAO = "BTN_AUTOMACAO"
BTN_SITE = "BTN_SITE"
BTN_MARKETING = "BTN_MARKETING"

# STEP 2A — AUTOMAÇÃO
BTN_AUTO_ATEND = "BTN_AUTO_ATEND"
BTN_AUTO_LEADS = "BTN_AUTO_LEADS"
BTN_AUTO_CRM = "BTN_AUTO_CRM"

# STEP 2B — SITE
BTN_SITE_INST = "BTN_SITE_INST"
BTN_SITE_LP = "BTN_SITE_LP"
BTN_SITE_ECOM = "BTN_SITE_ECOM"

# STEP 2C — MARKETING
BTN_MKT_POSIC = "BTN_MKT_POSIC"
BTN_MKT_TRAFEGO = "BTN_MKT_TRAFEGO"
BTN_MKT_SOCIAL = "BTN_MKT_SOCIAL"

# STEP 3 — PRAZO
BTN_PRAZO_URGENTE = "BTN_PRAZO_URGENTE"
BTN_PRAZO_30 = "BTN_PRAZO_30"
BTN_PRAZO_PLANEJ = "BTN_PRAZO_PLANEJ"

# STEP 4 — INVESTIMENTO
BTN_INV_1 = "BTN_INV_1"
BTN_INV_2 = "BTN_INV_2"
BTN_INV_INFO = "BTN_INV_INFO"

# (atalhos opcionais, se quiser usar no app.py pós-handoff)
BRIEF_RESTART = "BRIEF_RESTART"
TALK_HUMAN = "TALK_HUMAN"


# =========================
# Textos (iguais ao esqueleto)
# =========================
WELCOME_TEXT = (
    "Olá 👋\n"
    "Sou o assistente virtual da Mugô.\n\n"
    "A gente usa tecnologia para destravar o que está travado no seu negócio.\n\n"
    "Qual dessas frentes faz mais sentido agora?"
)

AUTO_TEXT = (
    "Perfeito.\n\n"
    "Automação é sobre ganhar tempo, escala e previsibilidade.\n\n"
    "Qual é o principal objetivo hoje?"
)

SITE_TEXT = (
    "Entendido.\n\n"
    "Um site bem estruturado aumenta credibilidade, alcance e conversão.\n\n"
    "Qual é o seu foco?"
)

MKT_TEXT = (
    "Perfeito.\n\n"
    "Estratégia é o que transforma presença em resultado.\n\n"
    "Qual é sua prioridade agora?"
)

PRAZO_TEXT = "Você tem um prazo ideal para colocar isso em funcionamento?"

INVEST_TEXT = (
    "Perfeito.\n\n"
    "Sobre investimento, você já tem uma faixa definida?"
)


FINAL_TEXT = (
    "Briefing recebido ✅\n\n"
    "Já organizei suas informações aqui internamente.\n\n"
    "A Julia vai assumir seu atendimento para estruturar a melhor solução para o seu caso.\n\n"
    "Se preferir adiantar, pode falar direto com ela aqui:\n"
    "👉 https://wa.me/5511973510549\n\n"
    "Vamos destravar isso com precisão."
)


# =========================
# Flow principal (NOVO)
# =========================
def handle_mugo_flow(wa_id: str, user_text: str, *, choice_id: str = "") -> Optional[Dict[str, Any]]:
    """
    Retorna dict com:
      - type: "buttons" | "text" | "handoff" | None
    """

    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    raw = _norm(choice_id or user_text)

    # =========================
    # ✅ Anti-estado legado / estado inválido
    # =========================
    allowed_states = {"step_01_welcome", "step_02_objetivo", "step_03_prazo", "step_04_invest"}
    if state and (state.startswith("mugo_") or state not in allowed_states):
        clear_flow(wa_id)
        state = ""
        data = {}

    # =========================
    # ✅ Pós-handoff: se usuário mandar msg depois, recomeça do zero
    # (Como o state fica vazio após concluir, isso já acontece.
    # Mas se por algum motivo ficou state inválido, o bloco acima reseta.)
    # =========================

    # ---------
    # Estado vazio -> STEP 01
    # ---------
    if not state:
        set_flow_state(wa_id, "step_01_welcome")
        return _btn(
            WELCOME_TEXT,
            [
                {"id": BTN_AUTOMACAO, "title": "Automação"},
                {"id": BTN_SITE, "title": "Site / Landing Page"},
                {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
            ],
        )

    # ---------
    # STEP 01 -> escolhe frente
    # ---------
    if state == "step_01_welcome":
        if raw in (BTN_AUTOMACAO, BTN_SITE, BTN_MARKETING):
            if raw == BTN_AUTOMACAO:
                merge_flow_data(wa_id, {"area_interesse": "automacao"})
                set_flow_state(wa_id, "step_02_objetivo")
                return _btn(
                    AUTO_TEXT,
                    [
                        {"id": BTN_AUTO_ATEND, "title": "Organizar atendimento"},
                        {"id": BTN_AUTO_LEADS, "title": "Gerar mais leads"},
                        {"id": BTN_AUTO_CRM, "title": "Integrar CRM / sistemas"},
                    ],
                )

            if raw == BTN_SITE:
                merge_flow_data(wa_id, {"area_interesse": "site"})
                set_flow_state(wa_id, "step_02_objetivo")
                return _btn(
                    SITE_TEXT,
                    [
                        {"id": BTN_SITE_INST, "title": "Institucional"},
                        {"id": BTN_SITE_LP, "title": "Landing Page de vendas"},
                        {"id": BTN_SITE_ECOM, "title": "E-commerce"},
                    ],
                )

            if raw == BTN_MARKETING:
                merge_flow_data(wa_id, {"area_interesse": "marketing"})
                set_flow_state(wa_id, "step_02_objetivo")
                return _btn(
                    MKT_TEXT,
                    [
                        {"id": BTN_MKT_POSIC, "title": "Posicionamento"},
                        {"id": BTN_MKT_TRAFEGO, "title": "Tráfego pago"},
                        {"id": BTN_MKT_SOCIAL, "title": "Social Media"},
                    ],
                )

        # se mandou texto em vez de clicar, reapresenta
        return _btn(
            WELCOME_TEXT,
            [
                {"id": BTN_AUTOMACAO, "title": "Automação"},
                {"id": BTN_SITE, "title": "Site / Landing Page"},
                {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
            ],
        )

    # ---------
    # STEP 02 -> escolhe sub_area e vai pro prazo
    # ---------
    if state == "step_02_objetivo":
        sub_map = {
            # automação
            BTN_AUTO_ATEND: "organizar_atendimento",
            BTN_AUTO_LEADS: "gerar_leads",
            BTN_AUTO_CRM: "integrar_crm",
            # site
            BTN_SITE_INST: "institucional",
            BTN_SITE_LP: "landing_page",
            BTN_SITE_ECOM: "ecommerce",
            # marketing
            BTN_MKT_POSIC: "posicionamento",
            BTN_MKT_TRAFEGO: "trafego_pago",
            BTN_MKT_SOCIAL: "social_media",
        }

        if raw in sub_map:
            merge_flow_data(wa_id, {"sub_area": sub_map[raw]})
            set_flow_state(wa_id, "step_03_prazo")
            return _btn(
                PRAZO_TEXT,
                [
                    {"id": BTN_PRAZO_URGENTE, "title": "O quanto antes"},
                    {"id": BTN_PRAZO_30, "title": "Até 30 dias"},
                    {"id": BTN_PRAZO_PLANEJ, "title": "Ainda planejando"},
                ],
            )

        # se deu ruim, volta nos botões conforme frente escolhida
        area = (data.get("area_interesse") or "").strip()
        if area == "automacao":
            return _btn(AUTO_TEXT, [
                {"id": BTN_AUTO_ATEND, "title": "Organizar atendimento"},
                {"id": BTN_AUTO_LEADS, "title": "Gerar mais leads"},
                {"id": BTN_AUTO_CRM, "title": "Integrar CRM / sistemas"},
            ])
        if area == "site":
            return _btn(SITE_TEXT, [
                {"id": BTN_SITE_INST, "title": "Institucional"},
                {"id": BTN_SITE_LP, "title": "Landing Page de vendas"},
                {"id": BTN_SITE_ECOM, "title": "E-commerce"},
            ])
        return _btn(MKT_TEXT, [
            {"id": BTN_MKT_POSIC, "title": "Posicionamento"},
            {"id": BTN_MKT_TRAFEGO, "title": "Tráfego pago"},
            {"id": BTN_MKT_SOCIAL, "title": "Social Media"},
        ])

    # ---------
    # STEP 03 -> prazo
    # ---------
    if state == "step_03_prazo":
        prazo_map = {
            BTN_PRAZO_URGENTE: "o quanto antes",
            BTN_PRAZO_30: "até 30 dias",
            BTN_PRAZO_PLANEJ: "ainda planejando",
        }
        if raw in prazo_map:
            merge_flow_data(wa_id, {"prazo": prazo_map[raw]})
            set_flow_state(wa_id, "step_04_invest")
            return _btn(
                INVEST_TEXT,
                [
                    {"id": BTN_INV_1, "title": "Nível 1"},
                    {"id": BTN_INV_2, "title": "Nível 2"},
                    {"id": BTN_INV_INFO, "title": "Quero entender as opções"},
                ],
            )

        # se mandou texto livre, aceita como prazo
        if raw:
            merge_flow_data(wa_id, {"prazo": raw[:80]})
            set_flow_state(wa_id, "step_04_invest")
            return _btn(
                INVEST_TEXT,
                [
                    {"id": BTN_INV_1, "title": "Nível 1"},
                    {"id": BTN_INV_2, "title": "Nível 2"},
                    {"id": BTN_INV_INFO, "title": "Quero entender as opções"},
                ],
            )

        return _text("Você pode me dizer o prazo em uma frase? (ex: até 30 dias)")

    # ---------
    # STEP 04 -> investimento e conclui (HANDOFF)
    # ---------
    if state == "step_04_invest":
        invest_map = {
            BTN_INV_1: "nível 1",
            BTN_INV_2: "nível 2",
            BTN_INV_INFO: "quer entender as opções",
        }
        if raw in invest_map:
            merge_flow_data(wa_id, {"investimento": invest_map[raw]})

            # pega data final
            final = get_flow(wa_id) or {}
            data2 = final.get("data") or {}
            summary = _build_summary(data2)

            # limpa flow pra próxima interação voltar pro STEP 01
            clear_flow(wa_id)

            return {
                "type": "handoff",
                "text": FINAL_TEXT,
                "topic": _build_topic(data2),
                "summary": summary,
            }

        # texto livre
        if raw:
            merge_flow_data(wa_id, {"investimento": raw[:80]})
            final = get_flow(wa_id) or {}
            data2 = final.get("data") or {}
            summary = _build_summary(data2)

            clear_flow(wa_id)

            return {
                "type": "handoff",
                "text": FINAL_TEXT,
                "topic": _build_topic(data2),
                "summary": summary,
            }

        return _text("Me diz rapidinho: nível 1, nível 2, ou quer entender as opções?")

    # fallback: se caiu num estado desconhecido, reseta
    clear_flow(wa_id)
    set_flow_state(wa_id, "step_01_welcome")
    return _btn(
        WELCOME_TEXT,
        [
            {"id": BTN_AUTOMACAO, "title": "Automação"},
            {"id": BTN_SITE, "title": "Site / Landing Page"},
            {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
        ],
    )


def _build_topic(data: Dict[str, Any]) -> str:
    area = (data.get("area_interesse") or "").strip().lower()
    if area == "automacao":
        return "Automação"
    if area == "site":
        return "Site / Landing Page"
    if area == "marketing":
        return "Estratégia & Marketing"
    return "Atendimento"


def _build_summary(data: Dict[str, Any]) -> str:
    area = _build_topic(data)
    sub = (data.get("sub_area") or "").strip()
    prazo = (data.get("prazo") or "").strip()
    inv = (data.get("investimento") or "").strip()

    lines = [f"Foco: {area}"]
    if sub:
        lines.append(f"Objetivo: {sub}")
    if prazo:
        lines.append(f"Prazo: {prazo}")
    if inv:
        lines.append(f"Investimento: {inv}")

    return "\n".join(lines)[:900]