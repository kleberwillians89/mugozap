from __future__ import annotations

from typing import Any, Dict, Optional

from services.state import get_flow, merge_flow_data, set_flow_state, clear_flow


def _btn(text: str, buttons: list[dict], step_key: str) -> Dict[str, Any]:
    return {"type": "buttons", "text": text, "buttons": buttons, "step_key": step_key}


def _text(text: str, step_key: str) -> Dict[str, Any]:
    return {"type": "text", "text": text, "step_key": step_key}


def _list(text: str, rows: list[dict], step_key: str) -> Dict[str, Any]:
    return {
        "type": "list",
        "text": text,
        "button": "Escolher",
        "sections": [{"title": "Como podemos ajudar", "rows": rows}],
        "step_key": step_key,
    }


def _norm(s: str) -> str:
    return (s or "").strip()


def _choice(raw: str) -> str:
    raw = _norm(raw)
    return raw.upper()


BTN_SITE_AUTO = "BTN_SITE_AUTO"
BTN_SOCIAL = "BTN_SOCIAL"
BTN_IA = "BTN_IA"

BTN_SITE_QUERO_SITE = "BTN_SITE_QUERO_SITE"
BTN_SITE_AUTOMATIZAR = "BTN_SITE_AUTOMATIZAR"
BTN_SITE_JA_TENHO_SITE = "BTN_SITE_JA_TENHO_SITE"

BTN_SOCIAL_TENHO_MARCA = "BTN_SOCIAL_TENHO_MARCA"
BTN_SOCIAL_MARCA_ZERO = "BTN_SOCIAL_MARCA_ZERO"
BTN_SOCIAL_CONSULTORIA = "BTN_SOCIAL_CONSULTORIA"

BTN_IA_IMAGENS = "BTN_IA_IMAGENS"
BTN_IA_IDEIA = "BTN_IA_IDEIA"
BTN_IA_CONSULTORIA = "BTN_IA_CONSULTORIA"

SERVICE_SITE = "service_site"
SERVICE_AUTOMATION = "service_automation"
SERVICE_AI = "service_ai"
SERVICE_TRAFFIC = "service_traffic"
SERVICE_BRANDING = "service_branding"
SERVICE_HUMAN = "service_human"

TEXT_OPTION_TO_SERVICE = {
    "1": SERVICE_SITE,
    "01": SERVICE_SITE,
    "2": SERVICE_AUTOMATION,
    "02": SERVICE_AUTOMATION,
    "3": SERVICE_AI,
    "03": SERVICE_AI,
    "4": SERVICE_TRAFFIC,
    "04": SERVICE_TRAFFIC,
    "5": SERVICE_BRANDING,
    "05": SERVICE_BRANDING,
    "6": SERVICE_HUMAN,
    "06": SERVICE_HUMAN,
}

SERVICE_CHOICES = {
    SERVICE_SITE: {
        "intent": "site",
        "topic": "Criar site ou landing page",
        "label": "Site/landing",
        "service_interest": "site",
    },
    SERVICE_AUTOMATION: {
        "intent": "automacao_whatsapp",
        "topic": "Automatizar WhatsApp/atendimento",
        "label": "Automação WhatsApp",
        "service_interest": "automacao_whatsapp",
    },
    SERVICE_AI: {
        "intent": "inteligencia_artificial",
        "topic": "Usar IA no meu negócio",
        "label": "IA no negócio",
        "service_interest": "inteligencia_artificial",
    },
    SERVICE_TRAFFIC: {
        "intent": "trafego_pago",
        "topic": "Tráfego pago/performance",
        "label": "Tráfego pago",
        "service_interest": "trafego_pago",
    },
    SERVICE_BRANDING: {
        "intent": "branding",
        "topic": "Branding/conteúdo/redes sociais",
        "label": "Branding/redes",
        "service_interest": "branding",
    },
    SERVICE_HUMAN: {
        "intent": "humano",
        "topic": "Falar com a equipe",
        "label": "Falar com equipe",
        "service_interest": "humano",
    },
}


STEP1_TEXT = (
    "Oi, tudo bem? Sou a assistente da Mugô. Como podemos te ajudar hoje?"
)

STEP2_TEXT = "Legal. Qual dessas opções mais se aproxima do que você precisa agora?"
STEP3_TEXT = "Perfeito. Me explica em uma frase o que você quer destravar agora."
STEP1_CLARIFY_TEXT = (
    "Posso te ajudar por três frentes: site e automação, social media ou inteligência artificial. "
    "Qual delas faz mais sentido agora?"
)

LOW_SIGNAL_INPUTS = {"oi", "ola", "olá", "opa", "tudo bem", "ajuda", "preciso de ajuda", "quero ajuda"}

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


def _reopen_step_01(wa_id: str, workspace_id: str = "") -> Dict[str, Any]:
    print(f"MUGO_FLOW:show_initial_menu wa_id={wa_id} workspace_id={workspace_id or '-'}")
    print(f"FLOW_MENU_SHOWN wa_id={wa_id} workspace_id={workspace_id or '-'}")
    set_flow_state(wa_id, "step_01", workspace_id=workspace_id)
    merge_flow_data(wa_id, {"current_step": "step_01", "bot_status": "bot_active", "waiting_for": "customer"}, workspace_id=workspace_id)
    return _list(
        STEP1_TEXT,
        [
            {"id": SERVICE_SITE, "title": "Site ou landing", "description": "Criar ou melhorar páginas"},
            {"id": SERVICE_AUTOMATION, "title": "Automatizar WhatsApp", "description": "Atendimento, leads e CRM"},
            {"id": SERVICE_AI, "title": "IA no negócio", "description": "Agentes, processos e escala"},
            {"id": SERVICE_TRAFFIC, "title": "Tráfego pago", "description": "Performance e anúncios"},
            {"id": SERVICE_BRANDING, "title": "Branding e redes", "description": "Conteúdo e posicionamento"},
            {"id": SERVICE_HUMAN, "title": "Falar com equipe", "description": "Encaminhar para a Mugô"},
        ],
        "step_01",
    )


def is_service_choice(choice_id: str) -> bool:
    key = _norm(choice_id).lower()
    return key in SERVICE_CHOICES or key in TEXT_OPTION_TO_SERVICE


def service_choice_context(choice_id: str) -> Dict[str, Any]:
    key = _norm(choice_id).lower()
    key = TEXT_OPTION_TO_SERVICE.get(key, key)
    data = SERVICE_CHOICES.get(key)
    if not data:
        return {}
    return {"id": key, **data}


def apply_service_choice(wa_id: str, choice_id: str, workspace_id: str = "") -> Dict[str, Any]:
    ctx = service_choice_context(choice_id)
    if not ctx:
        print(f"MUGO_FLOW:unknown_service_choice wa_id={wa_id} choice_id={choice_id}")
        return {}

    print(
        "MUGO_FLOW:service_choice "
        f"wa_id={wa_id} choice_id={ctx.get('id')} service_interest={ctx.get('service_interest')} intent={ctx.get('intent')}"
    )
    print(
        "FLOW_BUTTON_CLICKED "
        f"wa_id={wa_id} choice_id={choice_id} normalized_id={ctx.get('id')} service_interest={ctx.get('service_interest')}"
    )
    merge_flow_data(
        wa_id,
        {
            "selected_service_id": ctx["id"],
            "selected_service": ctx["service_interest"],
            "topic": ctx["topic"],
            "tema": ctx["service_interest"],
            "intent": ctx["intent"],
            "current_step": "ai_qualification",
            "bot_status": "ai_active",
            "waiting_for": "customer",
        },
        workspace_id=workspace_id,
    )
    set_flow_state(wa_id, "ai_qualification", workspace_id=workspace_id)
    return ctx


def _normalize_topic(picked: str, raw: str) -> str:
    if picked in {BTN_SITE_AUTO, "SITE_E_AUTOMACAO"}:
        return BTN_SITE_AUTO
    if picked in {BTN_SOCIAL, "SOCIAL_MEDIA"}:
        return BTN_SOCIAL
    if picked in {BTN_IA, "IA"}:
        return BTN_IA

    lower = _norm(raw).lower()
    if any(k in lower for k in ["site", "landing", "loja", "e-commerce", "autom", "crm", "whatsapp"]):
        return BTN_SITE_AUTO
    if any(k in lower for k in ["social", "instagram", "marca", "branding", "trafego", "tráfego"]):
        return BTN_SOCIAL
    if any(k in lower for k in ["ia", "inteligencia", "inteligência", "chatbot", "agente"]):
        return BTN_IA
    return ""


def _normalize_problem(state: str, picked: str, raw: str) -> str:
    if state == "step_02_site":
        if picked == BTN_SITE_QUERO_SITE or "site" in raw.lower():
            return BTN_SITE_QUERO_SITE
        if picked == BTN_SITE_AUTOMATIZAR or any(k in raw.lower() for k in ["automat", "crm", "processo", "whatsapp"]):
            return BTN_SITE_AUTOMATIZAR
        if picked == BTN_SITE_JA_TENHO_SITE or "já tenho" in raw.lower() or "ja tenho" in raw.lower():
            return BTN_SITE_JA_TENHO_SITE

    if state == "step_02_social":
        if picked == BTN_SOCIAL_TENHO_MARCA or "tenho uma marca" in raw.lower():
            return BTN_SOCIAL_TENHO_MARCA
        if picked == BTN_SOCIAL_MARCA_ZERO or "zero" in raw.lower() or "criar marca" in raw.lower():
            return BTN_SOCIAL_MARCA_ZERO
        if picked == BTN_SOCIAL_CONSULTORIA or "consult" in raw.lower():
            return BTN_SOCIAL_CONSULTORIA

    if state == "step_02_ia":
        if picked == BTN_IA_IMAGENS or any(k in raw.lower() for k in ["imagem", "video", "vídeo", "criativo"]):
            return BTN_IA_IMAGENS
        if picked == BTN_IA_IDEIA or "ideia" in raw.lower():
            return BTN_IA_IDEIA
        if picked == BTN_IA_CONSULTORIA or "consult" in raw.lower():
            return BTN_IA_CONSULTORIA

    return ""


def _is_low_signal_text(raw: str) -> bool:
    return _norm(raw).lower() in LOW_SIGNAL_INPUTS


def _advance_to_problem_step(wa_id: str, topic_key: str, workspace_id: str = "") -> Dict[str, Any]:
    if topic_key == BTN_SITE_AUTO:
        merge_flow_data(
            wa_id,
            {"tema": "site_e_automacao", "topic": "Site e automação", "current_step": "step_02_site", "bot_status": "bot_active", "waiting_for": "customer"},
            workspace_id=workspace_id,
        )
        set_flow_state(wa_id, "step_02_site", workspace_id=workspace_id)
        return _btn(
            STEP2_TEXT,
            [
                {"id": BTN_SITE_QUERO_SITE, "title": "Quero fazer um site"},
                {"id": BTN_SITE_AUTOMATIZAR, "title": "Automatizar processos"},
                {"id": BTN_SITE_JA_TENHO_SITE, "title": "Já tenho um site"},
            ],
            "step_02_site",
        )

    if topic_key == BTN_SOCIAL:
        merge_flow_data(
            wa_id,
            {"tema": "social_media", "topic": "Social media", "current_step": "step_02_social", "bot_status": "bot_active", "waiting_for": "customer"},
            workspace_id=workspace_id,
        )
        set_flow_state(wa_id, "step_02_social", workspace_id=workspace_id)
        return _btn(
            STEP2_TEXT,
            [
                {"id": BTN_SOCIAL_TENHO_MARCA, "title": "Tenho uma marca"},
                {"id": BTN_SOCIAL_MARCA_ZERO, "title": "Criar marca do zero"},
                {"id": BTN_SOCIAL_CONSULTORIA, "title": "Consultoria"},
            ],
            "step_02_social",
        )

    merge_flow_data(
        wa_id,
        {"tema": "ia", "topic": "Inteligência Artificial", "current_step": "step_02_ia", "bot_status": "bot_active", "waiting_for": "customer"},
        workspace_id=workspace_id,
    )
    set_flow_state(wa_id, "step_02_ia", workspace_id=workspace_id)
    return _btn(
        STEP2_TEXT,
        [
            {"id": BTN_IA_IMAGENS, "title": "Criar imagens/vídeos"},
            {"id": BTN_IA_IDEIA, "title": "Tenho uma ideia"},
            {"id": BTN_IA_CONSULTORIA, "title": "Consultoria"},
        ],
        "step_02_ia",
    )


def _advance_to_free_text(wa_id: str, option_key: str, raw: str, workspace_id: str = "") -> Dict[str, Any]:
    option_map = {
        BTN_SITE_QUERO_SITE: ("quero_fazer_um_site", "Quero fazer um site"),
        BTN_SITE_AUTOMATIZAR: ("automatizar_processos", "Automatizar processos"),
        BTN_SITE_JA_TENHO_SITE: ("ja_tenho_um_site", "Já tenho um site"),
        BTN_SOCIAL_TENHO_MARCA: ("tenho_uma_marca", "Tenho uma marca"),
        BTN_SOCIAL_MARCA_ZERO: ("criar_marca_do_zero", "Criar marca do zero"),
        BTN_SOCIAL_CONSULTORIA: ("consultoria", "Consultoria"),
        BTN_IA_IMAGENS: ("criar_imagens_videos", "Criar imagens e vídeos"),
        BTN_IA_IDEIA: ("tenho_uma_ideia", "Tenho uma ideia"),
        BTN_IA_CONSULTORIA: ("consultoria", "Consultoria"),
    }
    option_value, problem_label = option_map.get(option_key, (_norm(raw)[:180], _norm(raw)[:180]))
    merge_flow_data(
        wa_id,
        {"opcao": option_value, "problem": problem_label, "current_step": "step_03_coleta", "bot_status": "bot_active", "waiting_for": "customer"},
        workspace_id=workspace_id,
    )
    set_flow_state(wa_id, "step_03_coleta", workspace_id=workspace_id)
    return _text(STEP3_TEXT, "step_03_coleta")


def handle_mugo_flow(wa_id: str, user_text: str, *, choice_id: str = "", workspace_id: str = "") -> Optional[Dict[str, Any]]:
    flow = get_flow(wa_id, workspace_id=workspace_id) or {}
    state = (flow.get("state") or "").strip()
    data = flow.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    raw = _norm(choice_id or user_text)
    picked = _choice(choice_id or user_text)
    print(
        "MUGO_FLOW:handle "
        f"wa_id={wa_id} state={state or '-'} choice_id={choice_id or '-'} raw={raw[:120]!r}"
    )

    if not state:
        return _reopen_step_01(wa_id, workspace_id=workspace_id)

    if state == "step_01":
        if is_service_choice(choice_id or user_text):
            ctx = apply_service_choice(wa_id, choice_id or user_text, workspace_id=workspace_id)
            print(
                "MUGO_FLOW:release_to_ai "
                f"wa_id={wa_id} service_interest={ctx.get('service_interest')} choice_id={choice_id or user_text}"
            )
            return {
                "type": "ai_context",
                "step_key": "service_selected",
                "service_context": ctx,
            }

        topic_key = _normalize_topic(picked, raw)
        if topic_key:
            print(f"MUGO_FLOW:return_fixed_response wa_id={wa_id} state=step_01 topic_key={topic_key}")
            return _advance_to_problem_step(wa_id, topic_key, workspace_id=workspace_id)

        print(f"MUGO_FLOW:return_clarify wa_id={wa_id} state=step_01")
        return _text(STEP1_CLARIFY_TEXT, "step_01_clarify")

    if state == "step_02_site":
        problem_key = _normalize_problem(state, picked, raw)
        if problem_key:
            return _advance_to_free_text(wa_id, problem_key, raw, workspace_id=workspace_id)
        if raw:
            return _advance_to_free_text(wa_id, "", raw, workspace_id=workspace_id)
        return _text(STEP2_TEXT, "step_02_site")

    if state == "step_02_social":
        problem_key = _normalize_problem(state, picked, raw)
        if problem_key:
            return _advance_to_free_text(wa_id, problem_key, raw, workspace_id=workspace_id)
        if raw:
            return _advance_to_free_text(wa_id, "", raw, workspace_id=workspace_id)
        return _text(STEP2_TEXT, "step_02_social")

    if state == "step_02_ia":
        problem_key = _normalize_problem(state, picked, raw)
        if problem_key:
            return _advance_to_free_text(wa_id, problem_key, raw, workspace_id=workspace_id)
        if raw:
            return _advance_to_free_text(wa_id, "", raw, workspace_id=workspace_id)
        return _text(STEP2_TEXT, "step_02_ia")

    if state == "step_03_coleta":
        briefing = raw
        if not briefing or _is_low_signal_text(briefing):
            return _text("Me conta em uma frase o que você quer resolver agora, para eu seguir com contexto.", "step_03_coleta")

        merge_flow_data(
            wa_id,
            {"briefing": briefing[:1200], "free_text_need": briefing[:1200], "current_step": "handoff_ready", "bot_status": "handoff_pending", "waiting_for": "human"},
            workspace_id=workspace_id,
        )

        final = get_flow(wa_id, workspace_id=workspace_id) or {}
        data2 = final.get("data") or {}
        summary = _build_summary(data2)

        clear_flow(wa_id, workspace_id=workspace_id)

        return {
            "type": "handoff",
            "text": "Perfeito. Já vou te encaminhar. ✅",
            "topic": _build_topic(data2),
            "summary": summary,
            "step_key": "handoff_ready",
        }

    clear_flow(wa_id, workspace_id=workspace_id)
    return _reopen_step_01(wa_id, workspace_id=workspace_id)


def _build_topic(data: Dict[str, Any]) -> str:
    tema = (data.get("tema") or "").strip().lower()
    if tema == "site_e_automacao":
        return "Site e automação"
    if tema == "social_media":
        return "Social media"
    if tema == "ia":
        return "Inteligência Artificial"
    return "Atendimento"


def _humanize_option(opcao: str) -> str:
    mapa = {
        "quero_fazer_um_site": "Quero fazer um site",
        "automatizar_processos": "Automatizar processos",
        "ja_tenho_um_site": "Já tenho um site",
        "tenho_uma_marca": "Tenho uma marca",
        "criar_marca_do_zero": "Criar marca do zero",
        "consultoria": "Consultoria",
        "criar_imagens_videos": "Criar imagens e vídeos",
        "tenho_uma_ideia": "Tenho uma ideia",
    }
    return mapa.get((opcao or "").strip(), (opcao or "").strip())


def _build_summary(data: Dict[str, Any]) -> str:
    tema = (data.get("topic") or "").strip() or _build_topic(data)
    opcao = (data.get("problem") or "").strip() or _humanize_option(data.get("opcao") or "")
    briefing = (data.get("briefing") or "").strip()

    lines = [f"Tema: {tema}"]
    if opcao:
        lines.append(f"Opção: {opcao}")
    if briefing:
        lines.append(f"Contexto: {briefing}")

    return "\n".join(lines)[:1500]
