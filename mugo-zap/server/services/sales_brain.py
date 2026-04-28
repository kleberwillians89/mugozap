from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List


FIELD_KEYS = [
    "service_interest",
    "intent",
    "main_goal",
    "desired_result",
    "site_scope",
    "lead_source",
    "current_tools",
    "current_status",
    "current_problem",
    "business_type",
    "business_name",
    "urgency",
    "budget_signal",
    "funnel_stage",
    "last_question_asked",
    "last_question_category",
    "next_best_question",
    "meeting_suggested",
    "briefing_ready",
    "briefing_sent_at",
    "handoff",
    "handoff_reason",
    "handoff_sent_at",
    "lead_temperature",
    "next_action",
]


def default_lead_state() -> Dict[str, Any]:
    return {
        "service_interest": None,
        "intent": None,
        "main_goal": None,
        "desired_result": None,
        "site_scope": None,
        "lead_source": None,
        "current_tools": None,
        "current_status": None,
        "current_problem": None,
        "business_type": None,
        "business_name": None,
        "urgency": None,
        "budget_signal": None,
        "funnel_stage": None,
        "last_question_asked": None,
        "last_question_category": None,
        "next_best_question": None,
        "meeting_suggested": False,
        "briefing_ready": False,
        "briefing_sent_at": None,
        "handoff": False,
        "handoff_reason": None,
        "handoff_sent_at": None,
        "lead_fields": {},
    }


SERVICE_CHOICES = {
    "1": ("site", "site", "site_scope", "Perfeito. Você quer criar uma página nova do zero ou melhorar uma página que já existe?"),
    "01": ("site", "site", "site_scope", "Perfeito. Você quer criar uma página nova do zero ou melhorar uma página que já existe?"),
    "service_site": ("site", "site", "site_scope", "Perfeito. Você quer criar uma página nova do zero ou melhorar uma página que já existe?"),
    "2": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Perfeito. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "02": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Perfeito. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "service_automation": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Perfeito. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "3": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "03": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "service_ai": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "4": ("trafego_pago", "trafego_pago", "current_status", "Perfeito. Hoje vocês já anunciam ou querem começar do zero?"),
    "04": ("trafego_pago", "trafego_pago", "current_status", "Perfeito. Hoje vocês já anunciam ou querem começar do zero?"),
    "service_traffic": ("trafego_pago", "trafego_pago", "current_status", "Perfeito. Hoje vocês já anunciam ou querem começar do zero?"),
    "5": ("branding", "branding", "main_goal", "Legal. A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?"),
    "05": ("branding", "branding", "main_goal", "Legal. A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?"),
    "service_branding": ("branding", "branding", "main_goal", "Legal. A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?"),
    "6": ("humano", "humano", "handoff", "Claro. Vou te encaminhar para a Julia com um resumo do que você precisa."),
    "06": ("humano", "humano", "handoff", "Claro. Vou te encaminhar para a Julia com um resumo do que você precisa."),
    "service_human": ("humano", "humano", "handoff", "Claro. Vou te encaminhar para a Julia com um resumo do que você precisa."),
}

CHOICE_ID_BY_SERVICE = {
    "site": "service_site",
    "automacao_whatsapp": "service_automation",
    "inteligencia_artificial": "service_ai",
    "trafego_pago": "service_traffic",
    "branding": "service_branding",
    "humano": "service_human",
}

INTENT_BY_SERVICE = {
    "site": "site",
    "automacao_whatsapp": "automacao_whatsapp",
    "inteligencia_artificial": "inteligencia_artificial",
    "trafego_pago": "trafego_pago",
    "branding": "branding",
    "humano": "humano",
}

MENU_TEXT_PATTERNS = {
    "site": [
        "service_site",
        "1",
        "01",
        "site",
        "pagina",
        "landing",
        "site ou landing",
        "criar ou melhorar paginas",
        "criar ou melhorar pagina",
        "criar paginas",
        "melhorar paginas",
    ],
    "automacao_whatsapp": [
        "service_automation",
        "2",
        "02",
        "automacao",
        "automatizar",
        "automatizar whatsapp",
        "automatizar atendimento",
        "whatsapp/atendimento",
        "atendimento automatico",
        "whatsapp",
        "zap",
    ],
    "inteligencia_artificial": [
        "service_ai",
        "3",
        "03",
        "ia",
        "ia no negocio",
        "inteligencia artificial",
        "agentes",
        "agentes processos e escala",
        "processos e escala",
    ],
    "trafego_pago": [
        "service_traffic",
        "4",
        "04",
        "trafego",
        "trafego pago",
        "performance",
        "anuncios",
        "performance e anuncios",
        "ads",
    ],
    "branding": [
        "service_branding",
        "5",
        "05",
        "branding",
        "marca",
        "conteudo",
        "redes sociais",
        "social media",
        "identidade",
        "posicionamento",
    ],
    "humano": [
        "service_human",
        "6",
        "06",
        "humano",
        "pessoa",
        "atendente",
        "falar com a equipe",
        "falar com humano",
        "falar com alguem",
        "julia",
    ],
}


def normalize_text(text: str) -> str:
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^\w\s/]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _has_any(text: str, terms: List[str]) -> bool:
    return any(term in text for term in terms)


def _match_menu_service(value: str) -> tuple[str, str]:
    norm = normalize_text(value)
    if not norm:
        return "", "low"
    for service, patterns in MENU_TEXT_PATTERNS.items():
        if norm in patterns:
            return service, "high"
    for service, patterns in MENU_TEXT_PATTERNS.items():
        for pattern in patterns:
            if len(pattern) >= 4 and (pattern in norm or norm in pattern):
                return service, "medium"
    return "", "low"


def _append_source(current: Any, source: str) -> str:
    parts = []
    for item in re.split(r",| e |\+|/", str(current or "")):
        item = item.strip()
        if item:
            parts.append(item)
    if source and source not in parts:
        parts.append(source)
    return " e ".join(parts)


def _service_candidate_from_text(text: str) -> str:
    if _has_any(text, ["landing", "pagina", "site"]):
        return "site"
    if _has_any(text, ["whatsapp", "whats", "zap", "automacao", "automatizar", "atendimento"]):
        return "automacao_whatsapp"
    if re.search(r"\bia\b", text) or _has_any(text, ["inteligencia artificial", "agente"]):
        return "inteligencia_artificial"
    if _has_any(text, ["trafego", "anuncio", "ads", "performance"]):
        return "trafego_pago"
    if _has_any(text, ["branding", "marca", "conteudo", "redes sociais"]):
        return "branding"
    return ""


def _explicit_service_switch(text: str) -> bool:
    return _has_any(
        text,
        [
            "na verdade quero falar de",
            "muda para",
            "mudar para",
            "trocar para",
            "quero trocar para",
            "nao e ia e",
            "nao e automacao e",
            "nao e site e",
            "quero falar de",
            "agora quero",
            "na verdade e",
        ],
    )


def detect_explicit_service_switch(text: str) -> bool:
    return _explicit_service_switch(normalize_text(text))


def normalize_inbound_choice(
    text: str | None = None,
    button_id: str | None = None,
    button_title: str | None = None,
    list_id: str | None = None,
    list_title: str | None = None,
    list_description: str | None = None,
    current_state: dict | None = None,
) -> Dict[str, Any]:
    state = flatten_state(current_state or {})
    locked_service = state.get("service_interest") or state.get("selected_service") or ""
    candidates = [
        ("list_id", list_id),
        ("button_id", button_id),
        ("list_title", list_title),
        ("button_title", button_title),
        ("list_description", list_description),
        ("text", text),
    ]
    raw_text = ""
    for _, value in candidates:
        if str(value or "").strip():
            raw_text = str(value or "").strip()
            break

    best_service = ""
    best_confidence = "low"
    best_source = ""
    for source, value in candidates:
        value = str(value or "").strip()
        if not value:
            continue
        service, confidence = _match_menu_service(value)
        if not service:
            continue
        if source == "text" and locked_service and service != locked_service and not detect_explicit_service_switch(value):
            print(f"SALES_BRAIN_SERVICE_LOCKED service={locked_service} ignored_candidate={service} source=text text={value[:160]!r}")
            continue
        best_service = service
        best_confidence = "high" if source in {"list_id", "button_id"} and confidence != "low" else confidence
        best_source = source
        break

    if locked_service and best_service and best_service != locked_service and not detect_explicit_service_switch(raw_text):
        source_is_visual_click = best_source in {"list_id", "button_id", "list_title", "button_title", "list_description"}
        if not source_is_visual_click:
            print(f"SALES_BRAIN_SERVICE_LOCKED service={locked_service} ignored_candidate={best_service} source={best_source} text={raw_text[:160]!r}")
            best_service = ""
            best_confidence = "low"
            best_source = ""

    return {
        "raw_text": raw_text,
        "normalized_text": normalize_text(raw_text),
        "choice_id": CHOICE_ID_BY_SERVICE.get(best_service),
        "service_interest": best_service or None,
        "intent": INTENT_BY_SERVICE.get(best_service),
        "is_menu_choice": bool(best_service and best_confidence in {"high", "medium"}),
        "confidence": best_confidence,
        "source": best_source or "text",
    }


def flatten_state(state: Dict[str, Any] | None) -> Dict[str, Any]:
    src = state or {}
    fields = src.get("lead_fields") if isinstance(src.get("lead_fields"), dict) else {}
    flat = {}
    for key in FIELD_KEYS:
        value = src.get(key)
        if value in (None, "", [], {}) and key in fields:
            value = fields.get(key)
        flat[key] = value
    flat["lead_fields"] = dict(fields)
    flat["selected_service"] = src.get("selected_service") or fields.get("service_interest") or flat.get("service_interest")
    flat["selected_service_id"] = src.get("selected_service_id") or ""
    return flat


def service_choice_update(choice_id: str) -> Dict[str, Any]:
    key = normalize_text(choice_id)
    service_from_text, confidence = _match_menu_service(key)
    if service_from_text and confidence == "high":
        key = CHOICE_ID_BY_SERVICE.get(service_from_text, key)
    if key not in SERVICE_CHOICES:
        return {}
    service, intent, category, question = SERVICE_CHOICES[key]
    updates = {
        "service_interest": service,
        "intent": intent,
        "funnel_stage": "qualificacao",
        "last_question_asked": question,
        "last_question_category": category,
        "next_best_question": question,
        "next_action": "ask_question",
    }
    if service == "humano":
        updates.update(
            {
                "handoff": True,
                "handoff_reason": "lead_pediu_humano",
                "lead_temperature": "hot",
                "meeting_suggested": True,
                "briefing_ready": True,
                "next_action": "handoff",
            }
        )
    return updates


def extract_signal_from_message(text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_text(text)
    state = flatten_state(current_state)
    last_category = state.get("last_question_category") or ""
    service = state.get("service_interest") or state.get("selected_service") or ""
    updates: Dict[str, Any] = {}

    choice_updates = service_choice_update(norm)
    if choice_updates:
        choice_service = choice_updates.get("service_interest") or ""
        if service and choice_service and choice_service != service and not detect_explicit_service_switch(text):
            print(f"SALES_BRAIN_SERVICE_LOCKED service={service} ignored_candidate={choice_service} source=text text={text[:160]!r}")
        else:
            updates.update(choice_updates)
            return updates

    if _has_any(norm, ["humano", "pessoa", "atendente", "julia", "falar com alguem", "quero falar", "falar com a equipe"]):
        updates.update(
            {
                "handoff": True,
                "handoff_reason": "lead_pediu_humano",
                "lead_temperature": "hot",
                "meeting_suggested": True,
                "briefing_ready": True,
                "next_action": "handoff",
                "funnel_stage": "handoff",
            }
        )

    candidate_service = _service_candidate_from_text(norm)
    if not service and candidate_service:
        updates.update({"service_interest": candidate_service, "intent": candidate_service, "funnel_stage": "qualificacao"})
    elif service and candidate_service and candidate_service != service:
        if _explicit_service_switch(norm):
            updates.update({"service_interest": candidate_service, "intent": candidate_service, "funnel_stage": "qualificacao"})
            print(f"SALES_BRAIN_SERVICE_SWITCH from={service} to={candidate_service} text={text[:160]!r}")
        else:
            print(f"SALES_BRAIN_SERVICE_LOCKED service={service} ignored_candidate={candidate_service} text={text[:160]!r}")
    elif service and candidate_service:
        print(f"SALES_BRAIN_SERVICE_LOCKED service={service} contextual_candidate={candidate_service} text={text[:160]!r}")

    service = updates.get("service_interest") or service

    if service == "site" or last_category == "site_scope":
        if service == "site" and last_category == "site_scope" and _has_any(norm, ["whatsapp", "whats", "zap"]):
            updates["desired_result"] = "usar WhatsApp como canal de conversão"
            updates["current_problem"] = updates.get("current_problem") or "página precisa levar as pessoas para o WhatsApp"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=desired_result value='usar WhatsApp como canal de conversão' text={text[:160]!r}")
        if _has_any(norm, ["do zero", "nova", "novo", "nova pagina", "criar", "criar do zero", "comecar", "fazer uma nova"]):
            updates["site_scope"] = "criar do zero"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=site_scope value='criar do zero' text={text[:160]!r}")
        elif _has_any(norm, ["melhorar", "melhorar uma pagina", "ja existe", "existe", "existente", "refazer", "otimizar", "arrumar", "reformular"]):
            updates["site_scope"] = "melhorar existente"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=site_scope value='melhorar existente' text={text[:160]!r}")

    if service == "trafego_pago" or last_category == "current_status":
        if _has_any(norm, ["ja anuncio", "ja anunciam", "ja anunciamos", "rodo anuncio", "tenho campanha", "anuncio hoje", "anunciamos", "campanha ativa"]):
            updates["current_status"] = "já anuncia"
            updates["current_tools"] = updates.get("current_tools") or "já anuncia"
        elif _has_any(norm, ["do zero", "comecar do zero", "nunca anunciei", "ainda nao", "nao anuncio"]):
            updates["current_status"] = "começar do zero"

    if (
        service == "inteligencia_artificial"
        and last_category in {"main_goal", "current_problem"}
        and _has_any(norm, ["atendimento", "redes sociais", "rede social", "conteudo", "processo", "vendas"])
    ):
        updates["current_problem"] = text.strip()[:180]
        if _has_any(norm, ["redes sociais", "rede social", "conteudo"]):
            updates["main_goal"] = "atendimento/conteúdo"
        elif "atendimento" in norm:
            updates["main_goal"] = "atendimento/processos internos"
        updates["funnel_stage"] = "qualificacao"
        print(f"SALES_BRAIN_CONTEXT_SIGNAL category={last_category} field=current_problem text={text[:160]!r}")
    elif _has_any(norm, ["vendas", "vender", "vender mais", "mais clientes", "leads", "gerar leads", "converter mais"]):
        updates["main_goal"] = "vendas/leads"
        updates["desired_result"] = "vender mais / gerar mais oportunidades"
        updates["funnel_stage"] = "qualificacao"
    elif _has_any(norm, ["tempo", "ganhar tempo", "responder rapido", "operacao", "automatizar processo"]):
        updates["main_goal"] = "operacao/tempo"
        updates["funnel_stage"] = "qualificacao"
    elif _has_any(norm, ["organizar", "crm", "funil", "acompanhar leads"]):
        updates["main_goal"] = "gestao/comercial"
        updates["funnel_stage"] = "qualificacao"
    elif _has_any(norm, ["posicionamento", "conteudo"]) or (service == "branding" and "marca" in norm):
        updates["main_goal"] = "marca/conteudo"
        updates["funnel_stage"] = "qualificacao"

    source = state.get("lead_source") or ""
    if "instagram" in norm or "insta" in norm:
        source = _append_source(source, "Instagram")
    if "whatsapp" in norm or "whats" in norm or "zap" in norm:
        source = _append_source(source, "WhatsApp")
    if "site" in norm and (last_category == "lead_source" or source):
        source = _append_source(source, "Site")
    if "indicacao" in norm:
        source = _append_source(source, "Indicação")
    if source:
        updates["lead_source"] = source
        if last_category == "lead_source":
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=lead_source field=lead_source value={source!r} text={text[:160]!r}")

    if last_category == "current_tools" and _has_any(norm, ["whatsapp", "whats", "zap"]) and not updates.get("current_tools"):
        updates["current_tools"] = "WhatsApp"
        print(f"SALES_BRAIN_CONTEXT_SIGNAL category=current_tools field=current_tools value='WhatsApp' text={text[:160]!r}")

    if _has_any(norm, ["manual", "na mao", "sem crm", "planilha", "caderno"]):
        updates["current_tools"] = "manual"
        if not state.get("current_problem"):
            updates["current_problem"] = "processo manual"
        updates["funnel_stage"] = "qualificacao"
        if last_category == "current_tools":
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=current_tools field=current_tools value='manual' text={text[:160]!r}")
    else:
        for tool in ["hubspot", "pipedrive", "rd station", "kommo", "crm"]:
            if tool in norm:
                updates["current_tools"] = tool.upper() if tool == "crm" else tool
                if last_category == "current_tools":
                    print(f"SALES_BRAIN_CONTEXT_SIGNAL category=current_tools field=current_tools value={updates['current_tools']!r} text={text[:160]!r}")
                break

    if _has_any(norm, ["essa semana", "urgente", "pra ja", "o quanto antes", "hoje", "amanha"]):
        updates["urgency"] = "alta"
        updates["funnel_stage"] = "decisao"
    elif _has_any(norm, ["esse mes", "este mes"]):
        updates["urgency"] = "media"
        updates["funnel_stage"] = "decisao"
    elif _has_any(norm, ["so vendo", "entendendo", "sem pressa"]):
        updates["urgency"] = "baixa"

    if _has_any(norm, ["tenho verba", "tenho orcamento", "tenho budget", "ja tenho verba"]):
        updates["budget_signal"] = "tem verba"
    elif _has_any(norm, ["sem verba", "baixo custo", "barato"]):
        updates["budget_signal"] = "sensível a preço"

    return updates


def merge_state(old_state: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old_state or {})
    fields = dict(merged.get("lead_fields") or {})
    for key, value in (updates or {}).items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
        if key in FIELD_KEYS and key not in {"meeting_suggested", "briefing_ready", "handoff"}:
            fields[key] = value
    merged["lead_fields"] = fields
    return merged


def get_next_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    service = state.get("service_interest") or state.get("selected_service") or ""
    offer = {
        "category": "offer_meeting",
        "question": "Perfeito, já tenho um bom contexto. Posso encaminhar um resumo para a Julia e agilizar o próximo passo?",
        "next_action": "offer_meeting",
    }
    if state.get("handoff") or service == "humano":
        return {"category": "handoff", "question": "Claro. Vou te encaminhar para a Julia com um resumo do que você precisa.", "next_action": "handoff"}
    if service == "site":
        if not state.get("site_scope"):
            return {"category": "site_scope", "question": "Perfeito. Você quer criar uma página nova do zero ou melhorar uma página que já existe?", "next_action": "ask_question"}
        if not state.get("main_goal"):
            return {"category": "main_goal", "question": "O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?", "next_action": "ask_question"}
        if not state.get("urgency"):
            return {"category": "urgency", "question": "Você tem alguma data ou campanha em mente para colocar essa página no ar?", "next_action": "ask_question"}
        return offer
    if service == "automacao_whatsapp":
        if not state.get("lead_source"):
            return {"category": "lead_source", "question": "Hoje os contatos chegam mais pelo WhatsApp, Instagram ou site?", "next_action": "ask_question"}
        if not (state.get("current_tools") or state.get("current_problem")):
            return {"category": "current_tools", "question": "Hoje vocês atendem tudo manualmente ou já usam alguma ferramenta/CRM?", "next_action": "ask_question"}
        if not state.get("urgency"):
            return {"category": "urgency", "question": "Você quer colocar isso para rodar ainda este mês ou está só entendendo possibilidades?", "next_action": "ask_question"}
        return offer
    if service == "inteligencia_artificial":
        if not state.get("main_goal"):
            return {"category": "main_goal", "question": "Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?", "next_action": "ask_question"}
        if not state.get("current_problem"):
            return {"category": "current_problem", "question": "Qual processo hoje mais toma tempo da equipe?", "next_action": "ask_question"}
        context_text = normalize_text(f"{state.get('main_goal') or ''} {state.get('current_problem') or ''}")
        if not state.get("lead_source") and _has_any(context_text, ["atendimento", "vendas", "lead", "cliente"]):
            return {"category": "lead_source", "question": "Hoje esses contatos chegam mais pelo WhatsApp, Instagram ou site?", "next_action": "ask_question"}
        if not state.get("current_tools"):
            return {"category": "current_tools", "question": "Hoje vocês fazem isso manualmente ou já usam alguma ferramenta/CRM?", "next_action": "ask_question"}
        if not state.get("urgency"):
            return {"category": "urgency", "question": "Isso é prioridade para agora ou vocês ainda estão explorando possibilidades?", "next_action": "ask_question"}
        return offer
    if service == "trafego_pago":
        if not (state.get("current_status") or state.get("current_tools")):
            return {"category": "current_status", "question": "Hoje vocês já anunciam ou querem começar do zero?", "next_action": "ask_question"}
        if not state.get("main_goal"):
            return {"category": "main_goal", "question": "O foco é gerar leads, vender no site ou fortalecer a marca?", "next_action": "ask_question"}
        if not state.get("budget_signal"):
            return {"category": "budget_signal", "question": "Vocês já têm uma verba mensal pensada para mídia?", "next_action": "ask_question"}
        return offer
    if service == "branding":
        if not state.get("main_goal"):
            return {"category": "main_goal", "question": "A ideia é melhorar posicionamento, conteúdo para redes sociais ou identidade da marca?", "next_action": "ask_question"}
        if not state.get("current_problem"):
            return {"category": "current_problem", "question": "Hoje o maior incômodo é falta de clareza na marca, falta de conteúdo ou pouca conversão?", "next_action": "ask_question"}
        if not state.get("urgency"):
            return {"category": "urgency", "question": "Você quer iniciar isso agora ou está planejando para os próximos meses?", "next_action": "ask_question"}
        return offer
    return {"category": "service_interest", "question": "Pra eu te direcionar melhor: você procura site, automação, IA, tráfego ou branding?", "next_action": "ask_question"}


def question_category(text: str) -> str:
    norm = normalize_text(text)
    if (
        "prioridade e pagina" in norm
        or ("pagina" in norm and "whatsapp" in norm and "marca" in norm)
        or ("procura" in norm and "automacao" in norm and "branding" in norm)
    ):
        return "service_interest"
    if "pagina nova" in norm or "melhorar uma pagina" in norm:
        return "site_scope"
    if "vendas/leads" in norm or "vender mais" in norm or "gerar leads" in norm or "foco e gerar" in norm:
        return "main_goal"
    if "whatsapp" in norm and ("instagram" in norm or "site" in norm or "canal" in norm):
        return "lead_source"
    if "manual" in norm or "ferramenta" in norm or "crm" in norm or "ja anunciam" in norm:
        return "current_tools" if "anunciam" not in norm else "current_status"
    if "data" in norm or "campanha" in norm or "este mes" in norm or "curto prazo" in norm or "prioridade" in norm:
        return "urgency"
    if "verba" in norm or "midia" in norm or "orcamento" in norm:
        return "budget_signal"
    if "julia" in norm and ("resumo" in norm or "encaminhar" in norm):
        return "offer_meeting"
    return ""


def is_forbidden_generic_reply(reply: str, state: Dict[str, Any] | None = None) -> bool:
    current = flatten_state(state or {})
    if not current.get("service_interest"):
        return False
    norm = normalize_text(reply)
    forbidden = [
        "pra eu te direcionar melhor a prioridade e pagina whatsapp ia anuncios ou marca",
        "voce procura site automacao ia trafego ou branding",
        "isso impacta mais vendas/leads ou operacao/tempo",
        "isso impacta mais vendas leads ou operacao tempo",
    ]
    return any(item in norm for item in forbidden)


def is_forbidden_generic_question(reply: str, state: Dict[str, Any] | None = None) -> bool:
    return is_forbidden_generic_reply(reply, state)


def is_duplicate_question(reply: str, last_question: str) -> bool:
    a = normalize_text(reply)
    b = normalize_text(last_question)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.86


def _category_answered(state: Dict[str, Any], category: str) -> bool:
    state = flatten_state(state)
    if category == "current_tools":
        return bool(state.get("current_tools"))
    if category == "current_status":
        return bool(state.get("current_status") or state.get("current_tools"))
    if category == "offer_meeting":
        return False
    return bool(state.get(category))


def validate_reply(reply: str, state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    next_q = get_next_question(state)
    category = question_category(reply)
    blocked = False
    reason = ""
    if is_duplicate_question(reply, state.get("last_question_asked") or ""):
        blocked = True
        reason = "duplicate_last_question"
    elif is_forbidden_generic_reply(reply, state):
        blocked = True
        reason = "forbidden_generic_reply"
    elif category and _category_answered(state, category):
        blocked = True
        reason = f"known_{category}"
    elif category == "service_interest" and state.get("service_interest"):
        blocked = True
        reason = "known_service_interest"
    if blocked:
        return {**next_q, "reply": next_q["question"], "blocked": True, "reason": reason}
    return {**next_q, "reply": reply, "blocked": False, "reason": ""}


def validate_final_reply(reply: str, state: Dict[str, Any]) -> Dict[str, Any]:
    return validate_reply(reply, state)


def should_handoff(state: Dict[str, Any], message: str) -> bool:
    updates = extract_signal_from_message(message, state)
    return bool(updates.get("handoff") or flatten_state(state).get("handoff"))


def _commercial_field_count(state: Dict[str, Any]) -> int:
    state = flatten_state(state)
    keys = ["main_goal", "desired_result", "site_scope", "lead_source", "current_tools", "current_problem", "urgency", "budget_signal", "current_status"]
    return sum(1 for key in keys if state.get(key))


def should_offer_meeting(state: Dict[str, Any]) -> bool:
    state = flatten_state(state)
    if get_next_question(state).get("next_action") == "offer_meeting":
        return True
    if state.get("urgency") == "alta" and state.get("service_interest") and _commercial_field_count(state) >= 2:
        return True
    if state.get("budget_signal") == "tem verba" and state.get("service_interest") and _commercial_field_count(state) >= 2:
        return True
    return False


def build_briefing(state: Dict[str, Any], recent_messages: list) -> Dict[str, Any]:
    state = flatten_state(state)
    summary_parts = []
    if state.get("service_interest"):
        summary_parts.append(f"Interesse: {state.get('service_interest')}")
    if state.get("main_goal"):
        summary_parts.append(f"Objetivo: {state.get('main_goal')}")
    if state.get("site_scope"):
        summary_parts.append(f"Escopo site: {state.get('site_scope')}")
    if state.get("lead_source"):
        summary_parts.append(f"Origem dos leads: {state.get('lead_source')}")
    if state.get("current_tools"):
        summary_parts.append(f"Ferramentas/processo: {state.get('current_tools')}")
    if state.get("current_problem"):
        summary_parts.append(f"Problema: {state.get('current_problem')}")
    if state.get("urgency"):
        summary_parts.append(f"Urgência: {state.get('urgency')}")
    if state.get("budget_signal"):
        summary_parts.append(f"Orçamento: {state.get('budget_signal')}")

    return {
        "summary": "; ".join(summary_parts) or "Lead iniciou conversa no WhatsApp.",
        "pain_points": [state.get("current_problem")] if state.get("current_problem") else [],
        "goals": [state.get("desired_result") or state.get("main_goal")] if (state.get("desired_result") or state.get("main_goal")) else [],
        "recommended_solution": state.get("service_interest") or state.get("intent"),
        "urgency": state.get("urgency"),
        "budget_signal": state.get("budget_signal"),
        "questions_to_julia": ["Confirmar escopo, prioridade e próximo passo comercial."],
        "suggested_next_step": "Julia assumir ou agendar uma conversa curta.",
    }
