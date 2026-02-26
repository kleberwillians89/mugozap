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


def _is_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")


# =========================
# IDs (comandos internos)
# =========================
CTA_AUTOMACAO = "FLOW_AUTOMATIZAR"
CTA_SITE = "FLOW_SITE"
CTA_SOCIAL = "FLOW_SOCIAL"

RESTART_BRIEF = "BRIEF_RESTART"
TALK_HUMAN = "TALK_HUMAN"

ORIGEM_INDIC = "ORIGEM_INDIC"
ORIGEM_INSTAGRAM = "ORIGEM_IG"
ORIGEM_GOOGLE = "ORIGEM_GOOGLE"
ORIGEM_OUTRO = "ORIGEM_OUTRO"

PRAZO_7 = "PRAZO_7"
PRAZO_15 = "PRAZO_15"
PRAZO_30 = "PRAZO_30"
PRAZO_60 = "PRAZO_60"

INV_1 = "INV_1"
INV_2 = "INV_2"
INV_3 = "INV_3"
INV_4 = "INV_4"
INV_5 = "INV_5"


# =========================
# Mensagens
# =========================
INTRO = (
    "Oi! Eu sou a Mugô. 👋\n"
    "A gente desenha e implementa soluções em tecnologia (IA, automação, sites e crescimento).\n\n"
    "Me diz qual é o foco agora:"
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
    low = raw.lower()

    # ---------
    # Atalhos globais
    # ---------
    if raw == RESTART_BRIEF:
        clear_flow(wa_id)
        state = ""
        data = {}

    if raw == TALK_HUMAN:
        # força handoff mesmo sem briefing completo
        topic = (data.get("servico") or "Atendimento").strip()[:100]
        summary = _build_summary(data, partial=True)
        return {
            "type": "handoff",
            "text": "Perfeito. Vou te colocar com a Julia agora. ✅",
            "topic": topic,
            "summary": summary,
        }

    # ---------
    # Estado vazio -> manda INTRO + botões e seta state
    # ---------
    if not state:
        set_flow_state(wa_id, "mugo_cta")
        return _btn(
            INTRO,
            [
                {"id": CTA_AUTOMACAO, "title": "Automação"},
                {"id": CTA_SITE, "title": "Site / E-commerce"},
                {"id": CTA_SOCIAL, "title": "Social / Tráfego"},
            ],
        )

    # ---------
    # mugo_cta -> escolhe serviço
    # ---------
    if state == "mugo_cta":
        if raw in (CTA_AUTOMACAO, CTA_SITE, CTA_SOCIAL):
            serv = "automacao" if raw == CTA_AUTOMACAO else ("site" if raw == CTA_SITE else "social")
            merge_flow_data(wa_id, {"servico": serv})
            set_flow_state(wa_id, "mugo_prazo")
            return _btn(
                "Fechado. Qual prazo você pretende ter isso pronto?",
                [
                    {"id": PRAZO_7, "title": "Até 7 dias"},
                    {"id": PRAZO_15, "title": "15 dias"},
                    {"id": PRAZO_30, "title": "30 dias"},
                    {"id": PRAZO_60, "title": "60+ dias"},
                ],
            )

        # se mandou texto ao invés de clicar, devolve botões sem “prender”
        return _btn(
            "Só pra eu acertar rápido: qual é o foco?",
            [
                {"id": CTA_AUTOMACAO, "title": "Automação"},
                {"id": CTA_SITE, "title": "Site / E-commerce"},
                {"id": CTA_SOCIAL, "title": "Social / Tráfego"},
            ],
        )

    # ---------
    # prazo
    # ---------
    if state == "mugo_prazo":
        prazo_map = {
            PRAZO_7: "até 7 dias",
            PRAZO_15: "15 dias",
            PRAZO_30: "30 dias",
            PRAZO_60: "60+ dias",
        }
        prazo = prazo_map.get(raw) or _norm(user_text)
        if not prazo:
            return _text("Me diz o prazo em uma frase (ex: 30 dias).")

        merge_flow_data(wa_id, {"prazo": prazo})
        set_flow_state(wa_id, "mugo_invest")
        return _btn(
            "E o investimento estimado pra esse projeto?",
            [
                {"id": INV_1, "title": "Nível 1"},
                {"id": INV_2, "title": "Nível 2"},
                {"id": INV_3, "title": "Nível 3"},
                {"id": INV_4, "title": "Nível 4"},
                {"id": INV_5, "title": "Nível 5"},
            ],
        )

    # ---------
    # investimento
    # ---------
    if state == "mugo_invest":
        inv_map = {
            INV_1: "nível 1",
            INV_2: "nível 2",
            INV_3: "nível 3",
            INV_4: "nível 4",
            INV_5: "nível 5",
        }
        inv = inv_map.get(raw) or _norm(user_text)
        if not inv:
            return _text("Escolhe um nível de investimento 🙂")

        merge_flow_data(wa_id, {"invest": inv})
        set_flow_state(wa_id, "mugo_empresa")
        return _text("Qual o nome da empresa?")

    # ---------
    # empresa
    # ---------
    if state == "mugo_empresa":
        empresa = _norm(user_text)
        if not empresa:
            return _text("Me fala só o nome da empresa 🙂")

        merge_flow_data(wa_id, {"empresa": empresa})
        set_flow_state(wa_id, "mugo_instagram")
        return _text("Me manda o link do Instagram (ou @usuario).")

    # ---------
    # instagram
    # ---------
    if state == "mugo_instagram":
        ig = _norm(user_text)
        if not ig:
            return _text("Pode mandar o link do Instagram ou o @ 🙂")

        merge_flow_data(wa_id, {"instagram": ig})
        set_flow_state(wa_id, "mugo_origem")
        return _btn(
            "Como você conheceu a Mugô?",
            [
                {"id": ORIGEM_INDIC, "title": "Indicação"},
                {"id": ORIGEM_INSTAGRAM, "title": "Instagram"},
                {"id": ORIGEM_GOOGLE, "title": "Google"},
                {"id": ORIGEM_OUTRO, "title": "Outro"},
            ],
        )

    # ---------
    # origem -> conclui e retorna HANDOFF
    # ---------
    if state == "mugo_origem":
        origem_map = {
            ORIGEM_INDIC: "indicação",
            ORIGEM_INSTAGRAM: "instagram",
            ORIGEM_GOOGLE: "google",
            ORIGEM_OUTRO: "outro",
        }
        origem = origem_map.get(raw) or _norm(user_text)
        if not origem:
            return _text("De onde veio? (ex: indicação, instagram, google…)")

        merge_flow_data(wa_id, {"origem": origem})

        # monta resumo final
        final = get_flow(wa_id) or {}
        data2 = final.get("data") or {}
        topic = _build_topic(data2)
        summary = _build_summary(data2, partial=False)

        # limpa flow depois de concluir (pra não ficar preso)
        clear_flow(wa_id)

        return {
            "type": "handoff",
            "text": "Perfeito. Briefing recebido ✅ Vou te direcionar agora pra Julia continuar com você.",
            "topic": topic,
            "summary": summary,
        }

    # fallback
    return None


def _build_topic(data: Dict[str, Any]) -> str:
    serv = (data.get("servico") or "").strip().lower()
    if serv == "automacao":
        return "Automação"
    if serv == "site":
        return "Site / E-commerce"
    if serv == "social":
        return "Social / Tráfego"
    return "Atendimento"


def _build_summary(data: Dict[str, Any], *, partial: bool) -> str:
    serv = _build_topic(data)
    prazo = (data.get("prazo") or "").strip()
    inv = (data.get("invest") or "").strip()
    emp = (data.get("empresa") or "").strip()
    ig = (data.get("instagram") or "").strip()
    org = (data.get("origem") or "").strip()

    lines = [f"Foco: {serv}"]
    if prazo:
        lines.append(f"Prazo: {prazo}")
    if inv:
        lines.append(f"Investimento: {inv}")
    if emp:
        lines.append(f"Empresa: {emp}")
    if ig:
        lines.append(f"Instagram: {ig}")
    if org:
        lines.append(f"Origem: {org}")

    if partial:
        return " | ".join(lines)[:650]
    return "\n".join(lines)[:900]