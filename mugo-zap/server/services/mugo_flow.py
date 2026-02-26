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
# IDS
# =========================
# STEP 1 (temas)
BTN_SITE_AUTO = "BTN_SITE_AUTO"
BTN_SOCIAL = "BTN_SOCIAL"
BTN_IA = "BTN_IA"

# STEP 2 (opções por tema)
# Site e automação
BTN_SITE_QUERO_SITE = "BTN_SITE_QUERO_SITE"
BTN_SITE_AUTOMATIZAR = "BTN_SITE_AUTOMATIZAR"
BTN_SITE_JA_TENHO_SITE = "BTN_SITE_JA_TENHO_SITE"

# Social media
BTN_SOCIAL_TENHO_MARCA = "BTN_SOCIAL_TENHO_MARCA"
BTN_SOCIAL_MARCA_ZERO = "BTN_SOCIAL_MARCA_ZERO"
BTN_SOCIAL_CONSULTORIA = "BTN_SOCIAL_CONSULTORIA"

# Inteligência Artificial
BTN_IA_IMAGENS = "BTN_IA_IMAGENS"
BTN_IA_IDEIA = "BTN_IA_IDEIA"
BTN_IA_CONSULTORIA = "BTN_IA_CONSULTORIA"


# =========================
# TEXTOS (EXATOS DO MAPA)
# =========================
STEP1_TEXT = (
    "Oi, tudo bem? Que bom te ver por aqui. Você entrou em contato para falar sobre qual desses temas?"
)

STEP2_TEXT = "Legal! Qual dessas opções se parece com o seu problema?"

# mensagens após escolha (EXATAS)
MSG_ENCAMINHA_NEGOCIO = (
    "Beleza, a gente pode te ajudar. Vou te encaminhar para um dos responsáveis, mas antes, me fala um pouco sobre o seu negócio"
)

MSG_ENCAMINHA_NEGOCIO_2 = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, me fala um pouco sobre o seu negócio"
)

MSG_ENCAMINHA_LINK_SITE = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, compartilha aqui o link do seu site, por favor."
)

MSG_ENCAMINHA_LINK_SITE_2 = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, compartilha aqui o link do seu site, por favor."
)

MSG_ENCAMINHA_CONTA_MARCA = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, me conta um pouco sobre a marca que você está criando"
)

MSG_ENCAMINHA_SEU_IG = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, compartilha aqui o seu @, caso você já tenha."
)

MSG_ENCAMINHA_NECESSIDADE = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, me conta um pouco sobre a sua necessidade"
)

MSG_ENCAMINHA_IDEIA = (
    "Beleza, vou te encaminhar para uma pessoa responsável. Mas antes, me conta um pouco sobre a sua ideia"
)

MSG_ENCAMINHA_ALGUEM = (
    "Beleza, vou te encaminhar para alguém que entende do assunto"
)


# =========================
# Flow
# =========================
def handle_mugo_flow(wa_id: str, user_text: str, *, choice_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    raw = _norm(choice_id or user_text)

    # =========================
    # ✅ Se o usuário mandar msg depois do fim, recomeça do zero
    # (como clear_flow zera de verdade agora, isso funciona)
    # =========================
    if not state:
        set_flow_state(wa_id, "step_01")

        return _btn(
            STEP1_TEXT,
            [
                {"id": BTN_SITE_AUTO, "title": "Site e automação"},
                {"id": BTN_SOCIAL, "title": "Social media"},
                # >20 antes: "Inteligência Artificial"
                {"id": BTN_IA, "title": "Inteligência (IA)"},
            ],
        )

    # =========================
    # STEP 01 -> escolhe tema
    # =========================
    if state == "step_01":
        if raw == BTN_SITE_AUTO:
            merge_flow_data(wa_id, {"tema": "site_e_automacao"})
            set_flow_state(wa_id, "step_02_site")
            return _btn(
                STEP2_TEXT,
                [
                    {"id": BTN_SITE_QUERO_SITE, "title": "Quero fazer um site"},
                    # >20 antes: "Preciso automatizar processos"
                    {"id": BTN_SITE_AUTOMATIZAR, "title": "Automatizar processos"},
                    # >20 antes: "Já tenho um site e quero falar sobre isso"
                    {"id": BTN_SITE_JA_TENHO_SITE, "title": "Já tenho um site"},
                ],
            )

        if raw == BTN_SOCIAL:
            merge_flow_data(wa_id, {"tema": "social_media"})
            set_flow_state(wa_id, "step_02_social")
            return _btn(
                STEP2_TEXT,
                [
                    # >20 antes: "Tenho/sou uma marca e preciso de ajuda"
                    {"id": BTN_SOCIAL_TENHO_MARCA, "title": "Tenho uma marca"},
                    # >20 antes: "Quero criar uma marca do zero"
                    {"id": BTN_SOCIAL_MARCA_ZERO, "title": "Criar marca do zero"},
                    {"id": BTN_SOCIAL_CONSULTORIA, "title": "Quero consultoria"},
                ],
            )

        if raw == BTN_IA:
            merge_flow_data(wa_id, {"tema": "ia"})
            set_flow_state(wa_id, "step_02_ia")
            return _btn(
                STEP2_TEXT,
                [
                    # >20 antes: "Quero criar imagens e vídeos"
                    {"id": BTN_IA_IMAGENS, "title": "Criar imagens/vídeos"},
                    # >20 antes: "Tenho uma ideia e quero colocar em prática"
                    {"id": BTN_IA_IDEIA, "title": "Tenho uma ideia"},
                    {"id": BTN_IA_CONSULTORIA, "title": "Quero uma consultoria"},
                ],
            )

        # se mandou texto (não clique), reapresenta
        clear_flow(wa_id)
        return None

    # =========================
    # STEP 02 (Site e automação)
    # =========================
    if state == "step_02_site":
        if raw == BTN_SITE_QUERO_SITE:
            merge_flow_data(wa_id, {"opcao": "quero_fazer_um_site"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_NEGOCIO)

        if raw == BTN_SITE_AUTOMATIZAR:
            merge_flow_data(wa_id, {"opcao": "automatizar_processos"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_NEGOCIO_2)

        if raw == BTN_SITE_JA_TENHO_SITE:
            merge_flow_data(wa_id, {"opcao": "ja_tenho_um_site"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_LINK_SITE)

        # inválido -> reinicia
        clear_flow(wa_id)
        return None

    # =========================
    # STEP 02 (Social)
    # =========================
    if state == "step_02_social":
        if raw == BTN_SOCIAL_TENHO_MARCA:
            merge_flow_data(wa_id, {"opcao": "tenho_uma_marca"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_LINK_SITE_2)

        if raw == BTN_SOCIAL_MARCA_ZERO:
            merge_flow_data(wa_id, {"opcao": "criar_marca_do_zero"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_CONTA_MARCA)

        if raw == BTN_SOCIAL_CONSULTORIA:
            merge_flow_data(wa_id, {"opcao": "consultoria"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_SEU_IG)

        clear_flow(wa_id)
        return None

    # =========================
    # STEP 02 (IA)
    # =========================
    if state == "step_02_ia":
        if raw == BTN_IA_IMAGENS:
            merge_flow_data(wa_id, {"opcao": "criar_imagens_videos"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_NECESSIDADE)

        if raw == BTN_IA_IDEIA:
            merge_flow_data(wa_id, {"opcao": "tenho_uma_ideia"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_IDEIA)

        if raw == BTN_IA_CONSULTORIA:
            merge_flow_data(wa_id, {"opcao": "consultoria"})
            set_flow_state(wa_id, "step_03_coleta")
            return _text(MSG_ENCAMINHA_ALGUEM)

        clear_flow(wa_id)
        return None

    # =========================
    # STEP 03 -> coleta texto livre e HANDOFF
    # =========================
    if state == "step_03_coleta":
        briefing = _norm(user_text)
        if not briefing:
            return _text("Pode me mandar uma frase com o contexto, por favor 🙂")

        merge_flow_data(wa_id, {"briefing": briefing[:1200]})

        final = get_flow(wa_id) or {}
        data2 = final.get("data") or {}
        summary = _build_summary(data2)

        # ✅ encerra fluxo (e agora realmente zera no banco)
        clear_flow(wa_id)

        return {
            "type": "handoff",
            "text": "Perfeito. Já vou te encaminhar. ✅",
            "topic": _build_topic(data2),
            "summary": summary,
        }

    # fallback
    clear_flow(wa_id)
    return None


def _build_topic(data: Dict[str, Any]) -> str:
    tema = (data.get("tema") or "").strip().lower()
    if tema == "site_e_automacao":
        return "Site e automação"
    if tema == "social_media":
        return "Social media"
    if tema == "ia":
        return "Inteligência Artificial"
    return "Atendimento"


def _build_summary(data: Dict[str, Any]) -> str:
    tema = _build_topic(data)
    opcao = (data.get("opcao") or "").strip()
    briefing = (data.get("briefing") or "").strip()

    lines = [f"Tema: {tema}"]
    if opcao:
        lines.append(f"Opção: {opcao}")
    if briefing:
        lines.append(f"Contexto: {briefing}")

    return "\n".join(lines)[:1500]