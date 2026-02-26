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
# IDs (botões/ações)
# =========================
# STEP 1
BTN_AUTOMACAO = "BTN_AUTOMACAO"
BTN_SITE = "BTN_SITE"
BTN_MARKETING = "BTN_MARKETING"

# Backwards compatibility (IDs antigos que ainda podem chegar em logs)
CTA_AUTOMACAO_OLD = "FLOW_AUTOMATIZAR"
CTA_SITE_OLD = "FLOW_SITE"
CTA_SOCIAL_OLD = "FLOW_SOCIAL"

# STEP 2A — Automação (objetivo)
BTN_AUTO_ATEND = "BTN_AUTO_ATEND"
BTN_AUTO_LEADS = "BTN_AUTO_LEADS"
BTN_AUTO_CRM = "BTN_AUTO_CRM"

# STEP 2B — Site (foco)
BTN_SITE_INST = "BTN_SITE_INST"
BTN_SITE_LP = "BTN_SITE_LP"
BTN_SITE_ECOM = "BTN_SITE_ECOM"

# STEP 2C — Marketing (prioridade)
BTN_MKT_POSIC = "BTN_MKT_POSIC"
BTN_MKT_TRAFEGO = "BTN_MKT_TRAFEGO"
BTN_MKT_SOCIAL = "BTN_MKT_SOCIAL"

# STEP 3 — Prazo
BTN_PRAZO_URGENTE = "BTN_PRAZO_URGENTE"
BTN_PRAZO_30 = "BTN_PRAZO_30"
BTN_PRAZO_PLANEJ = "BTN_PRAZO_PLANEJ"

# STEP 4 — Investimento
BTN_INV_1 = "BTN_INV_1"
BTN_INV_2 = "BTN_INV_2"
BTN_INV_INFO = "BTN_INV_INFO"

# Ações pós-handoff (usadas no app.py)
RESTART_BRIEF = "BRIEF_RESTART"
TALK_HUMAN = "TALK_HUMAN"


# =========================
# Textos (esqueleto)
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
    "A Julia vai assumir seu atendimento para estruturar a melhor solução para o seu caso."
)


# =========================
# Flow principal
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

    # =========================================
    # Atalhos globais (pós-handoff)
    # =========================================
    # Se o cliente clicar "Preencher novamente" (BRIEF_RESTART),
    # reinicia do zero, SEM depender de "voltar".
    if raw == RESTART_BRIEF:
        clear_flow(wa_id)
        state = ""
        data = {}

    # Botão "Falar com Julia" (TALK_HUMAN): gera handoff mesmo se não terminou.
    if raw == TALK_HUMAN:
        topic = (_build_topic(data) or "Atendimento").strip()[:100]
        summary = _build_summary(data, partial=True)
        clear_flow(wa_id)
        return {
            "type": "handoff",
            "text": "Perfeito. Vou te colocar com a Julia agora. ✅",
            "topic": topic,
            "summary": summary,
        }

    # =========================================
    # Regra de ouro:
    # Se state estiver vazio -> sempre volta pro STEP 1 (boas-vindas + botões)
    #
    # Isso garante: depois do handoff/link, qualquer nova mensagem reinicia do zero.
    # =========================================
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

    # =========================================
    # STEP 01 — WELCOME (seleção da frente)
    # =========================================
    if state == "step_01_welcome":
        # aceita ids novos e antigos
        if raw in (BTN_AUTOMACAO, CTA_AUTOMACAO_OLD):
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

        if raw in (BTN_SITE, CTA_SITE_OLD):
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

        if raw in (BTN_MARKETING, CTA_SOCIAL_OLD):
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

        # Se o cliente respondeu texto ao invés de clicar, reapresenta
        return _btn(
            "Pra eu acertar rápido: qual dessas frentes faz mais sentido agora?",
            [
                {"id": BTN_AUTOMACAO, "title": "Automação"},
                {"id": BTN_SITE, "title": "Site / Landing Page"},
                {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
            ],
        )

    # =========================================
    # STEP 02 — OBJETIVO / SUBÁREA
    # =========================================
    if state == "step_02_objetivo":
        area = (data.get("area_interesse") or "").strip().lower()

        # Automação
        if area == "automacao":
            sub_map = {
                BTN_AUTO_ATEND: "Organizar atendimento",
                BTN_AUTO_LEADS: "Gerar mais leads",
                BTN_AUTO_CRM: "Integrar CRM / sistemas",
            }
            sub = sub_map.get(raw, "")
            if not sub:
                return _btn(
                    "Qual é o principal objetivo hoje?",
                    [
                        {"id": BTN_AUTO_ATEND, "title": "Organizar atendimento"},
                        {"id": BTN_AUTO_LEADS, "title": "Gerar mais leads"},
                        {"id": BTN_AUTO_CRM, "title": "Integrar CRM / sistemas"},
                    ],
                )
            merge_flow_data(wa_id, {"sub_area": sub})
            set_flow_state(wa_id, "step_03_prazo")
            return _btn(
                PRAZO_TEXT,
                [
                    {"id": BTN_PRAZO_URGENTE, "title": "O quanto antes"},
                    {"id": BTN_PRAZO_30, "title": "Até 30 dias"},
                    {"id": BTN_PRAZO_PLANEJ, "title": "Ainda planejando"},
                ],
            )

        # Site
        if area == "site":
            sub_map = {
                BTN_SITE_INST: "Institucional",
                BTN_SITE_LP: "Landing Page de vendas",
                BTN_SITE_ECOM: "E-commerce",
            }
            sub = sub_map.get(raw, "")
            if not sub:
                return _btn(
                    "Qual é o seu foco?",
                    [
                        {"id": BTN_SITE_INST, "title": "Institucional"},
                        {"id": BTN_SITE_LP, "title": "Landing Page de vendas"},
                        {"id": BTN_SITE_ECOM, "title": "E-commerce"},
                    ],
                )
            merge_flow_data(wa_id, {"sub_area": sub})
            set_flow_state(wa_id, "step_03_prazo")
            return _btn(
                PRAZO_TEXT,
                [
                    {"id": BTN_PRAZO_URGENTE, "title": "O quanto antes"},
                    {"id": BTN_PRAZO_30, "title": "Até 30 dias"},
                    {"id": BTN_PRAZO_PLANEJ, "title": "Ainda planejando"},
                ],
            )

        # Marketing
        if area == "marketing":
            sub_map = {
                BTN_MKT_POSIC: "Posicionamento",
                BTN_MKT_TRAFEGO: "Tráfego pago",
                BTN_MKT_SOCIAL: "Social Media",
            }
            sub = sub_map.get(raw, "")
            if not sub:
                return _btn(
                    "Qual é sua prioridade agora?",
                    [
                        {"id": BTN_MKT_POSIC, "title": "Posicionamento"},
                        {"id": BTN_MKT_TRAFEGO, "title": "Tráfego pago"},
                        {"id": BTN_MKT_SOCIAL, "title": "Social Media"},
                    ],
                )
            merge_flow_data(wa_id, {"sub_area": sub})
            set_flow_state(wa_id, "step_03_prazo")
            return _btn(
                PRAZO_TEXT,
                [
                    {"id": BTN_PRAZO_URGENTE, "title": "O quanto antes"},
                    {"id": BTN_PRAZO_30, "title": "Até 30 dias"},
                    {"id": BTN_PRAZO_PLANEJ, "title": "Ainda planejando"},
                ],
            )

        # Se por algum motivo perdeu a área, reinicia
        clear_flow(wa_id)
        return _btn(
            WELCOME_TEXT,
            [
                {"id": BTN_AUTOMACAO, "title": "Automação"},
                {"id": BTN_SITE, "title": "Site / Landing Page"},
                {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
            ],
        )

    # =========================================
    # STEP 03 — PRAZO
    # =========================================
    if state == "step_03_prazo":
        prazo_map = {
            BTN_PRAZO_URGENTE: "O quanto antes",
            BTN_PRAZO_30: "Até 30 dias",
            BTN_PRAZO_PLANEJ: "Ainda planejando",
        }
        prazo = prazo_map.get(raw) or _norm(user_text)
        if not prazo:
            return _text("Qual prazo ideal? (ex: Até 30 dias)")

        merge_flow_data(wa_id, {"prazo": prazo})
        set_flow_state(wa_id, "step_04_invest")
        return _btn(
            INVEST_TEXT,
            [
                {"id": BTN_INV_1, "title": "Nível 1"},
                {"id": BTN_INV_2, "title": "Nível 2"},
                {"id": BTN_INV_INFO, "title": "Quero entender as opções"},
            ],
        )

    # =========================================
    # STEP 04 — INVESTIMENTO
    # =========================================
    if state == "step_04_invest":
        inv_map = {
            BTN_INV_1: "Nível 1",
            BTN_INV_2: "Nível 2",
            BTN_INV_INFO: "Quero entender as opções",
        }
        inv = inv_map.get(raw) or _norm(user_text)
        if not inv:
            return _text("Me diz a faixa de investimento (ou escolha um botão).")

        merge_flow_data(wa_id, {"investimento": inv})

        # Conclui: monta resumo, limpa flow e retorna HANDOFF
        final = get_flow(wa_id) or {}
        data2 = final.get("data") or {}
        topic = _build_topic(data2)
        summary = _build_summary(data2, partial=False)

        clear_flow(wa_id)  # ✅ garante que qualquer próxima msg reinicia do zero

        return {
            "type": "handoff",
            "text": FINAL_TEXT,
            "topic": topic,
            "summary": summary,
        }

    # fallback: se caiu em estado desconhecido, reinicia
    clear_flow(wa_id)
    return _btn(
        WELCOME_TEXT,
        [
            {"id": BTN_AUTOMACAO, "title": "Automação"},
            {"id": BTN_SITE, "title": "Site / Landing Page"},
            {"id": BTN_MARKETING, "title": "Estratégia & Marketing"},
        ],
    )


# =========================
# Builders
# =========================
def _build_topic(data: Dict[str, Any]) -> str:
    area = (data.get("area_interesse") or "").strip().lower()
    if area == "automacao":
        return "Automação"
    if area == "site":
        return "Site / Landing Page"
    if area == "marketing":
        return "Estratégia & Marketing"
    return "Atendimento"


def _build_summary(data: Dict[str, Any], *, partial: bool) -> str:
    # Campos do esqueleto
    area = _build_topic(data)
    sub = (data.get("sub_area") or "").strip()
    prazo = (data.get("prazo") or "").strip()
    inv = (data.get("investimento") or "").strip()

    lines = [f"Área: {area}"]
    if sub:
        lines.append(f"Objetivo: {sub}")
    if prazo:
        lines.append(f"Prazo: {prazo}")
    if inv:
        lines.append(f"Investimento: {inv}")

    if partial:
        return " | ".join(lines)[:650]
    return "\n".join(lines)[:900]