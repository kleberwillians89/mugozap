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
    "conversation_memory",
    "discovery_memory",
    "primary_track",
    "related_needs",
    "solution",
    "objective",
    "pain",
    "process",
]


SERVICE_LABELS = {
    "ia_no_negocio": "IA no negócio",
    "site": "site/landing page",
    "automacao_whatsapp": "automação de WhatsApp",
    "inteligencia_artificial": "inteligência artificial",
    "trafego_pago": "tráfego pago/performance",
    "branding": "branding/comunicação",
    "humano": "atendimento humano",
}

RAW_LOW_SIGNAL_PHRASES = [
    "busco todas as frentes para ontem",
    "todas as frentes para ontem",
    "me ajudem por favor",
    "me ajuda por favor",
    "tudo",
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
        "conversation_memory": {},
        "discovery_memory": {},
        "primary_track": None,
        "related_needs": [],
        "solution": None,
        "objective": None,
        "pain": None,
        "process": None,
    }


SERVICE_CHOICES = {
    "1": ("site", "site", "site_scope", "Hoje a ideia é criar uma página nova do zero ou melhorar uma página que já existe?"),
    "01": ("site", "site", "site_scope", "Hoje a ideia é criar uma página nova do zero ou melhorar uma página que já existe?"),
    "service_site": ("site", "site", "site_scope", "Hoje a ideia é criar uma página nova do zero ou melhorar uma página que já existe?"),
    "2": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Boa. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "02": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Boa. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "service_automation": ("automacao_whatsapp", "automacao_whatsapp", "lead_source", "Boa. Hoje o atendimento de vocês acontece mais pelo WhatsApp, Instagram ou outro canal?"),
    "3": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "03": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "service_ai": ("inteligencia_artificial", "inteligencia_artificial", "main_goal", "Boa. Você imagina usar IA mais para atendimento, vendas, conteúdo ou processos internos?"),
    "4": ("trafego_pago", "trafego_pago", "current_status", "Legal. Hoje vocês já anunciam ou querem começar do zero?"),
    "04": ("trafego_pago", "trafego_pago", "current_status", "Legal. Hoje vocês já anunciam ou querem começar do zero?"),
    "service_traffic": ("trafego_pago", "trafego_pago", "current_status", "Legal. Hoje vocês já anunciam ou querem começar do zero?"),
    "5": ("branding", "branding", "main_goal", "Você quer fortalecer posicionamento, identidade visual ou conteúdo para redes?"),
    "05": ("branding", "branding", "main_goal", "Você quer fortalecer posicionamento, identidade visual ou conteúdo para redes?"),
    "service_branding": ("branding", "branding", "main_goal", "Você quer fortalecer posicionamento, identidade visual ou conteúdo para redes?"),
    "6": ("humano", "humano", "handoff", "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma."),
    "06": ("humano", "humano", "handoff", "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma."),
    "service_human": ("humano", "humano", "handoff", "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma."),
}

SITE_SCOPE_QUESTION = "Hoje a ideia é criar uma página nova do zero ou melhorar uma página que já existe?"
SITE_PROBLEM_QUESTION = "Hoje o maior incômodo é visual, conversão, velocidade, clareza da oferta ou organização das informações?"
SITE_EXISTING_SCOPE = "melhorar_site_existente"
SEMANTIC_EXISTING_SCOPE = "melhorar_existente"
SEMANTIC_CREATE_SCOPE = "criar_do_zero"

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


def _has_deadline_urgency(text: str) -> bool:
    if _has_any(text, ["essa semana", "urgente", "pra ja", "o quanto antes", "hoje", "amanha", "ate sexta", "até sexta"]):
        return True
    deadline_patterns = [
        r"\bate\s+(?:dia\s+)?\d{1,2}(?:/\d{1,2})?\b",
        r"\bpara\s+(?:dia\s+)?\d{1,2}(?:/\d{1,2})?\b",
        r"\bpra\s+(?:dia\s+)?\d{1,2}(?:/\d{1,2})?\b",
        r"\bdia\s+\d{1,2}\s+de\s+[a-z]+",
        r"\brodando\s+(?:ate|para|pra)\s+(?:dia\s+)?\d{1,2}",
    ]
    return any(re.search(pattern, text) for pattern in deadline_patterns)


def _explicit_field_change(text: str) -> bool:
    norm = normalize_text(text)
    return _has_any(norm, ["na verdade", "mudei de ideia", "trocar", "troca", "muda", "mudar", "nao e", "não é", "quero mudar"])


def _can_update_known_field(state: Dict[str, Any], key: str, value: Any, text: str) -> bool:
    current = flatten_state(state).get(key)
    if current in (None, "", [], {}) or value in (None, "", [], {}) or current == value:
        return True
    if _explicit_field_change(text) or detect_explicit_service_switch(text):
        return True
    print(f"SALES_BRAIN_FIELD_LOCKED field={key} current={current!r} incoming={value!r} text={str(text or '')[:160]!r}")
    return False


def _lock_known_field_updates(updates: Dict[str, Any], state: Dict[str, Any], text: str) -> Dict[str, Any]:
    locked = dict(updates or {})
    for key in ["service_interest", "main_goal", "lead_source", "current_tools", "current_status", "site_scope"]:
        if key in locked and not _can_update_known_field(state, key, locked.get(key), text):
            locked.pop(key, None)
    if locked.get("service_interest"):
        locked["intent"] = INTENT_BY_SERVICE.get(locked.get("service_interest"), locked.get("intent"))
    return locked


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


def _empty_conversation_memory() -> Dict[str, Any]:
    return {
        "canal": None,
        "atendimento": None,
        "objetivo": None,
        "gargalo": None,
        "volume": None,
        "tempo_resposta": None,
        "processo_comercial": None,
        "crm": None,
        "automacao": None,
        "orcamento": None,
    }


DISCOVERY_SCHEMAS = {
    "site": ["site_scope", "objetivo_pagina", "problema_site", "publico", "prazo", "orcamento"],
    "automacao_whatsapp": ["canal", "atendimento_atual", "objetivo", "gargalo", "volume", "crm", "orcamento"],
    "inteligencia_artificial": ["processo", "dor_operacional", "ferramenta_atual", "volume_tarefa", "objetivo_ia", "orcamento"],
    "trafego_pago": ["canal_atual", "objetivo_campanha", "verba", "oferta", "estrutura_atual", "problema_performance"],
    "branding": ["foco_marca", "estagio_marca", "objetivo_comunicacao", "produto_servico", "canal_principal", "dificuldade_atual", "orcamento"],
    "humano": [],
}


def _empty_discovery_memory() -> Dict[str, Any]:
    return {service: {key: None for key in keys} for service, keys in DISCOVERY_SCHEMAS.items()}


def _read_discovery_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    fields = state.get("lead_fields") if isinstance(state.get("lead_fields"), dict) else {}
    raw = state.get("discovery_memory") or fields.get("discovery_memory") or {}
    memory = _empty_discovery_memory()
    if isinstance(raw, dict):
        for service, values in raw.items():
            if service not in memory or not isinstance(values, dict):
                continue
            for key, value in values.items():
                if key in memory[service] and value not in (None, "", [], {}):
                    memory[service][key] = value
    return memory


def _read_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    fields = state.get("lead_fields") if isinstance(state.get("lead_fields"), dict) else {}
    raw = state.get("conversation_memory") or fields.get("conversation_memory") or {}
    memory = _empty_conversation_memory()
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in memory and value not in (None, "", [], {}):
                memory[key] = value
    return memory


def _memory_from_known_fields(state: Dict[str, Any], updates: Dict[str, Any] | None = None, text: str = "") -> Dict[str, Any]:
    merged = {**flatten_state(state), **(updates or {})}
    memory = _read_memory(state)
    norm = normalize_text(text)

    if merged.get("lead_source"):
        memory["canal"] = merged.get("lead_source")
    if merged.get("current_tools"):
        tools_norm = normalize_text(str(merged.get("current_tools") or ""))
        if "manual" in tools_norm:
            memory["atendimento"] = "manual"
            memory["automacao"] = memory.get("automacao") or "não identificada"
        elif tools_norm:
            memory["atendimento"] = merged.get("current_tools")
            if "crm" in tools_norm or tools_norm in {"hubspot", "pipedrive", "rd station", "kommo"}:
                memory["crm"] = merged.get("current_tools")
            else:
                memory["automacao"] = merged.get("current_tools")
    if merged.get("main_goal"):
        memory["objetivo"] = merged.get("main_goal")
    if merged.get("current_problem") and normalize_text(str(merged.get("current_problem"))) not in {"processo manual"}:
        memory["gargalo"] = merged.get("current_problem")
    if merged.get("budget_signal"):
        memory["orcamento"] = merged.get("budget_signal")

    volume_match = re.search(r"\b(\d{1,5})\s+(?:leads?|contatos?|mensagens?|atendimentos?)\b", norm)
    if volume_match:
        memory["volume"] = f"{volume_match.group(1)} contatos/leads"
    if _has_any(norm, ["muito lead", "muitos leads", "alto volume", "bastante mensagem", "muita mensagem"]):
        memory["volume"] = "alto volume percebido"
    if _has_any(norm, ["demora", "demoram", "responder rapido", "responder rápido", "tempo de resposta", "lead esfria", "esfriam"]):
        memory["tempo_resposta"] = "tempo de resposta é uma dor"
        memory["gargalo"] = memory.get("gargalo") or "tempo de resposta"
    if _has_any(norm, ["sem crm", "nao temos crm", "não temos crm", "planilha", "caderno"]):
        memory["crm"] = "não usa CRM"
        memory["processo_comercial"] = memory.get("processo_comercial") or "controle manual"
    elif _has_any(norm, ["crm", "hubspot", "pipedrive", "rd station", "kommo"]):
        memory["crm"] = merged.get("current_tools") or "usa CRM"
    if _has_any(norm, ["sem processo", "baguncado", "bagunçado", "perdemos lead", "perde lead", "perdendo lead"]):
        memory["processo_comercial"] = "processo comercial desorganizado"
        memory["gargalo"] = memory.get("gargalo") or "perda de leads no processo"
    return memory


def _discovery_from_known_fields(state: Dict[str, Any], updates: Dict[str, Any] | None = None, text: str = "") -> Dict[str, Any]:
    merged = {**flatten_state(state), **(updates or {})}
    memory = _read_discovery_memory(state)
    norm = normalize_text(text)
    service = merged.get("service_interest") or merged.get("selected_service") or ""

    site = memory["site"]
    if merged.get("site_scope"):
        site["site_scope"] = merged.get("site_scope")
    if merged.get("main_goal") and service == "site":
        site["objetivo_pagina"] = merged.get("main_goal")
    if merged.get("current_problem") and service == "site":
        site["problema_site"] = merged.get("current_problem")
    if merged.get("urgency"):
        site["prazo"] = merged.get("urgency")
    if merged.get("budget_signal"):
        site["orcamento"] = merged.get("budget_signal")

    automation = memory["automacao_whatsapp"]
    if merged.get("lead_source"):
        automation["canal"] = merged.get("lead_source")
    if merged.get("current_tools"):
        automation["atendimento_atual"] = merged.get("current_tools")
    if merged.get("main_goal") and service == "automacao_whatsapp":
        automation["objetivo"] = merged.get("main_goal")
    if merged.get("current_problem") and normalize_text(str(merged.get("current_problem"))) != "processo manual":
        automation["gargalo"] = merged.get("current_problem")
    if _has_any(norm, ["sem crm", "planilha", "caderno"]) or (merged.get("current_tools") and "crm" in normalize_text(str(merged.get("current_tools")))):
        automation["crm"] = merged.get("current_tools") or ("não usa CRM" if "sem crm" in norm else "usa CRM")
    volume_match = re.search(r"\b(\d{1,5})\s+(?:leads?|contatos?|mensagens?|atendimentos?|tarefas?)\b", norm)
    if volume_match:
        automation["volume"] = f"{volume_match.group(1)} contatos/leads"
        memory["inteligencia_artificial"]["volume_tarefa"] = f"{volume_match.group(1)} tarefas/ocorrências"
    if merged.get("budget_signal"):
        automation["orcamento"] = merged.get("budget_signal")

    ai = memory["inteligencia_artificial"]
    if service == "inteligencia_artificial":
        if merged.get("main_goal"):
            ai["objetivo_ia"] = merged.get("main_goal")
            ai["processo"] = ai.get("processo") or merged.get("main_goal")
        if merged.get("current_problem"):
            ai["dor_operacional"] = merged.get("current_problem")
        if merged.get("current_tools"):
            ai["ferramenta_atual"] = merged.get("current_tools")
        if merged.get("budget_signal"):
            ai["orcamento"] = merged.get("budget_signal")

    traffic = memory["trafego_pago"]
    if service == "trafego_pago":
        if merged.get("current_status"):
            traffic["estrutura_atual"] = merged.get("current_status")
            traffic["canal_atual"] = merged.get("current_status")
        if merged.get("main_goal"):
            traffic["objetivo_campanha"] = merged.get("main_goal")
        if merged.get("budget_signal"):
            traffic["verba"] = merged.get("budget_signal")
        if merged.get("current_problem"):
            traffic["problema_performance"] = merged.get("current_problem")
        if _has_any(norm, ["produto", "servico", "serviço", "oferta"]):
            traffic["oferta"] = text.strip()[:180]

    branding = memory["branding"]
    if service == "branding":
        if merged.get("main_goal"):
            branding["objetivo_comunicacao"] = branding.get("objetivo_comunicacao") or merged.get("main_goal")
            branding["foco_marca"] = branding.get("foco_marca") or merged.get("main_goal")
        if _has_any(norm, ["identidade da marca", "identidade visual", "identidade"]):
            branding["foco_marca"] = "identidade"
            branding["objetivo_comunicacao"] = branding.get("objetivo_comunicacao") or "clareza e consistência da marca"
        if _has_any(norm, ["criar uma marca", "criar marca", "marca para divulgar", "divulgar meus produtos", "divulgar produtos"]):
            branding["objetivo_comunicacao"] = "criar marca para divulgar produtos"
            branding["produto_servico"] = "produtos"
            branding["foco_marca"] = branding.get("foco_marca") or "construção de marca"
        if _has_any(norm, ["crescimento da minha marca", "aumentar crescimento", "crescer minha marca", "crescimento de marca", "aumentar o crescimento"]):
            branding["objetivo_comunicacao"] = "crescimento de marca"
            branding["foco_marca"] = branding.get("foco_marca") or "crescimento"
        if _has_any(norm, ["posicionamento"]):
            branding["foco_marca"] = branding.get("foco_marca") or "posicionamento"
        if _has_any(norm, ["conteudo", "conteúdo", "redes"]):
            branding["foco_marca"] = branding.get("foco_marca") or "conteúdo/redes"
        if _has_any(norm, ["nome", "identidade visual", "redes ativas", "ja tem", "já tem", "ja temos", "já temos"]):
            branding["estagio_marca"] = "já tem estrutura inicial"
        elif _has_any(norm, ["do zero", "estruturada do zero", "começando", "comecando", "sem identidade"]):
            branding["estagio_marca"] = "estruturada do zero"
        if _has_any(norm, ["vendidos hoje", "ja vendo", "já vendo", "vendemos", "vende hoje"]):
            branding["produto_servico"] = branding.get("produto_servico") or "produtos já vendidos"
        elif _has_any(norm, ["fase de lancamento", "fase de lançamento", "lancamento", "lançamento"]):
            branding["produto_servico"] = branding.get("produto_servico") or "produtos em lançamento"
        if _has_any(norm, ["instagram", "insta"]):
            branding["canal_principal"] = "Instagram"
        if merged.get("current_problem") and service == "branding":
            branding["dificuldade_atual"] = merged.get("current_problem")
        if merged.get("budget_signal"):
            branding["orcamento"] = merged.get("budget_signal")

    return memory


def _multi_short_answer(text: str) -> str:
    norm = normalize_text(text)
    if _has_any(norm, ["pelos 3", "pelos tres", "os 3", "os tres", "todos", "tudo"]):
        return "all"
    if _has_any(norm, ["os dois", "ambos", "quero fazer os dois", "fazer os dois"]):
        return "two"
    return ""


def _service_candidate_from_text(text: str) -> str:
    if _has_any(text, ["chatbot", "chat bot", "agente de ia", "agente ia", "inteligencia artificial", "inteligência artificial"]) or re.search(r"\bia\b", text):
        return "inteligencia_artificial"
    if _has_any(text, ["landing", "pagina", "site"]):
        return "site"
    if _has_any(text, ["whatsapp", "whats", "zap", "automacao", "automatizar", "atendimento"]):
        return "automacao_whatsapp"
    if re.search(r"\bia\b", text) or _has_any(text, ["inteligencia artificial", "agente"]):
        return "inteligencia_artificial"
    if _has_any(text, ["trafego", "anuncio", "ads", "performance"]):
        return "trafego_pago"
    if _has_any(text, ["branding", "marca", "identidade", "conteudo", "redes sociais", "instagram", "insta"]):
        return "branding"
    if _has_any(text, ["crm", "funil", "vendas", "comercial"]):
        return "automacao_whatsapp"
    return ""


def _is_existing_site_scope(text: str) -> bool:
    norm = normalize_text(text)
    if not norm:
        return False
    if _has_any(norm, ["do zero", "nova pagina", "pagina nova", "criar do zero", "comecar do zero", "fazer uma nova"]):
        return False
    existing_terms = [
        "melhorar site",
        "melhorar um site",
        "melhorar o site",
        "melhorar uma pagina",
        "melhorar pagina",
        "ja tenho site",
        "tenho site",
        "site ja existe",
        "ja existe",
        "existente",
        "quero melhorar",
        "otimizar site",
        "otimizar o site",
        "arrumar site",
        "reformular site",
        "refazer site",
    ]
    if _has_any(norm, existing_terms):
        return True
    return norm in {"site", "meu site", "o site", "pagina", "minha pagina", "melhorar"}


def _semantic_site_scope(text: str, state: Dict[str, Any]) -> tuple[str, float, str]:
    norm = normalize_text(text)
    if not norm:
        return "indefinido", 0.0, ""

    create_signals = [
        "comecar do zero",
        "começar do zero",
        "do zero",
        "nao tenho nada",
        "não tenho nada",
        "nao tenho site",
        "não tenho site",
        "ainda nao tenho",
        "ainda não tenho",
        "preciso criar",
        "criar uma landing",
        "criar landing",
        "landing nova",
        "pagina nova",
        "página nova",
        "lancar uma pagina",
        "lançar uma página",
        "lancar uma landing",
        "quero lancar",
        "quero lançar",
        "construir do inicio",
        "construir do início",
    ]
    existing_signals = [
        "ja tenho",
        "já tenho",
        "o que ja tenho",
        "o que já tenho",
        "meu site",
        "site existe",
        "ate existe",
        "até existe",
        "ja existe",
        "já existe",
        "site esta ruim",
        "site está ruim",
        "nao converte",
        "não converte",
        "nao vende",
        "não vende",
        "visual ta fraco",
        "visual tá fraco",
        "visual fraco",
        "dar uma melhorada",
        "melhorada",
        "melhorar",
        "arrumar",
        "otimizar",
        "reformular",
        "refazer",
        "pagina nao passa confianca",
        "página não passa confiança",
        "nao passa confianca",
        "não passa confiança",
        "fraco",
        "ruim",
    ]
    if _has_any(norm, create_signals):
        return SEMANTIC_CREATE_SCOPE, 0.86, "A resposta indica construção de uma página/base nova."
    if _has_any(norm, existing_signals):
        return SEMANTIC_EXISTING_SCOPE, 0.86, "A resposta indica que já existe uma base e a dor é melhorar desempenho, percepção ou conversão."
    if (state.get("service_interest") == "site" or state.get("last_question_category") == "site_scope") and norm in {"site", "pagina", "landing", "meu site"}:
        return SEMANTIC_EXISTING_SCOPE, 0.68, "Resposta curta dentro do contexto de site; assumo melhoria de uma base existente para avançar."
    return "indefinido", 0.35, "Não há sinal suficiente para decidir entre criar do zero e melhorar algo existente."


def _semantic_current_problem(text: str) -> str:
    norm = normalize_text(text)
    if not norm:
        return ""
    problem_map = [
        (["nao converte", "não converte", "conversao", "conversão", "nao vende", "não vende"], "site não converte bem"),
        (["visual", "fraco", "ruim", "feio", "antigo"], "visual fraco ou desalinhado"),
        (["confianca", "confiança", "credibilidade"], "página não passa confiança"),
        (["clareza", "oferta", "confuso", "confusa"], "clareza da oferta"),
        (["velocidade", "lento", "lenta", "carrega"], "velocidade ou performance"),
        (["organização", "organizacao", "informacoes", "informações"], "organização das informações"),
        (["arrumar", "melhorada", "melhorar", "otimizar", "reformular", "refazer"], "estrutura precisa ser melhorada"),
    ]
    for terms, label in problem_map:
        if _has_any(norm, terms):
            return label
    return ""


def _semantic_budget_signal(text: str) -> str:
    norm = normalize_text(text)
    if _has_any(norm, ["baixo custo", "barato", "pouca verba", "sem verba", "orcamento baixo", "orçamento baixo"]):
        return "baixo"
    if _has_any(norm, ["tenho verba", "tem verba", "orcamento", "orçamento", "budget", "investir"]):
        return "medio"
    if _has_any(norm, ["verba alta", "budget alto", "investimento alto"]):
        return "alto"
    return "indefinido"


def _semantic_intent(text: str, state: Dict[str, Any]) -> tuple[str, float]:
    norm = normalize_text(text)
    current_service = state.get("service_interest") or state.get("selected_service") or ""
    if current_service == "site":
        return "site_landing", 0.78
    if current_service == "automacao_whatsapp":
        return "whatsapp_automation", 0.78
    if current_service == "branding":
        return "branding", 0.74
    if current_service == "trafego_pago":
        return "traffic", 0.74
    if _has_any(norm, ["chatbot", "chat bot", "agente de ia", "agente ia", "inteligencia artificial", "inteligência artificial"]) or re.search(r"\bia\b", norm):
        return "ai_business", 0.84
    if _has_any(norm, ["site", "landing", "pagina", "página"]):
        return "site_landing", 0.76
    if _has_any(norm, ["whatsapp", "whats", "zap", "atendimento", "automacao", "automação", "bot"]):
        return "whatsapp_automation", 0.76
    if _has_any(norm, ["instagram", "insta", "conteudo", "conteúdo", "redes sociais", "social"]):
        return "social_media", 0.74
    if _has_any(norm, ["marca", "branding", "identidade", "posicionamento"]):
        return "branding", 0.74
    if _has_any(norm, ["trafego", "tráfego", "ads", "anuncio", "anúncio", "midia paga", "mídia paga"]):
        return "traffic", 0.74
    if _has_any(norm, ["crm", "funil", "relacionamento"]):
        return "crm", 0.72
    return "unknown", 0.3


def _question_was_answered(stage: str, extracted_fields: Dict[str, Any]) -> bool:
    if stage == "site_scope":
        return extracted_fields.get("site_scope") in {SEMANTIC_EXISTING_SCOPE, SEMANTIC_CREATE_SCOPE}
    if stage == "lead_source":
        return bool(extracted_fields.get("channel"))
    if stage in {"current_problem", "current_tools", "main_goal", "current_status"}:
        return any(extracted_fields.get(key) for key in ["current_problem", "channel"])
    if stage == "budget_signal":
        return extracted_fields.get("budget_signal") != "indefinido"
    return any(value not in (None, "", "indefinido") for value in extracted_fields.values())


def interpret_user_message(user_message: str, conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    state = flatten_state(conversation_context or {})
    norm = normalize_text(user_message)
    intent, intent_confidence = _semantic_intent(norm, state)
    site_scope, scope_confidence, scope_reason = _semantic_site_scope(norm, state)
    problem = _semantic_current_problem(norm)
    stage = state.get("last_question_category") or question_category(state.get("last_question_asked") or "")
    if stage == "site_scope" and problem == "estrutura precisa ser melhorada":
        problem = ""
    channel = ""
    if _has_any(norm, ["whatsapp", "whats", "zap"]):
        channel = "WhatsApp"
    elif _has_any(norm, ["instagram", "insta"]):
        channel = "Instagram"
    elif _has_any(norm, ["site"]):
        channel = "Site"

    budget_signal = _semantic_budget_signal(norm)
    extracted_fields = {
        "site_scope": site_scope,
        "current_problem": problem,
        "channel": channel,
        "budget_signal": budget_signal,
    }
    stage_answered = _question_was_answered(stage, extracted_fields)
    if stage == "site_scope":
        confidence = scope_confidence
    elif stage in {"service_interest", ""}:
        confidence = max(intent_confidence, scope_confidence if site_scope != "indefinido" else 0.0)
    else:
        confidence = max(intent_confidence, scope_confidence if site_scope != "indefinido" else 0.0)
    if stage_answered:
        confidence = max(confidence, 0.72)

    projected_state = merge_state(state, _updates_from_interpretation(extracted_fields, intent, state, user_message))
    next_question = get_next_question(projected_state).get("question") or ""
    if confidence < 0.65 and stage == "site_scope":
        next_question = "Para eu não te prender numa pergunta travada: hoje existe alguma página no ar ou a ideia é construir uma nova base?"

    reasoning = scope_reason or "Interpretação feita a partir do contexto comercial e da resposta do lead."
    return {
        "intent": intent,
        "stage_answered": bool(stage_answered),
        "extracted_fields": extracted_fields,
        "confidence": round(min(1.0, max(0.0, confidence)), 2),
        "reasoning_summary": reasoning,
        "next_best_question": next_question,
    }


def _updates_from_interpretation(
    extracted_fields: Dict[str, Any],
    intent: str,
    state: Dict[str, Any],
    user_message: str,
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    intent_to_service = {
        "ai_business": "inteligencia_artificial",
        "site_landing": "site",
        "whatsapp_automation": "automacao_whatsapp",
        "branding": "branding",
        "social_media": "branding",
        "traffic": "trafego_pago",
        "crm": "automacao_whatsapp",
    }
    service = state.get("service_interest") or state.get("selected_service") or ""
    candidate_service = intent_to_service.get(intent)
    if candidate_service and (not service or detect_explicit_service_switch(user_message)):
        updates["service_interest"] = candidate_service
        updates["intent"] = INTENT_BY_SERVICE.get(candidate_service, candidate_service)
        updates["funnel_stage"] = "qualificacao"

    semantic_scope = extracted_fields.get("site_scope")
    site_context = intent == "site_landing" or state.get("service_interest") == "site" or state.get("last_question_category") == "site_scope"
    if site_context and semantic_scope == SEMANTIC_EXISTING_SCOPE:
        updates["site_scope"] = SITE_EXISTING_SCOPE
    elif site_context and semantic_scope == SEMANTIC_CREATE_SCOPE:
        updates["site_scope"] = "criar do zero"

    if extracted_fields.get("current_problem"):
        updates["current_problem"] = extracted_fields["current_problem"]
    if extracted_fields.get("channel"):
        updates["lead_source"] = _append_source(state.get("lead_source"), extracted_fields["channel"])
    budget = extracted_fields.get("budget_signal")
    if budget == "baixo":
        updates["budget_signal"] = "sensível a preço"
    elif budget in {"medio", "alto"}:
        updates["budget_signal"] = "tem verba" if budget == "medio" else "alto potencial"
    return updates


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


def _is_pure_menu_number(text: str) -> bool:
    return normalize_text(text) in {"1", "2", "3", "4", "5", "6", "01", "02", "03", "04", "05", "06"}


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
    active_question = bool(state.get("last_question_category"))
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
        if source == "text" and not _is_pure_menu_number(value):
            continue
        if source == "text" and locked_service and not detect_explicit_service_switch(value) and not _is_pure_menu_number(value):
            print(
                f"SALES_BRAIN_SERVICE_LOCKED service={locked_service} "
                f"ignored_contextual_menu_candidate={service} source=text text={value[:160]!r}"
            )
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
    recent_questions = src.get("recent_bot_questions") or fields.get("recent_bot_questions") or []
    flat["recent_bot_questions"] = recent_questions if isinstance(recent_questions, list) else []
    memory = src.get("conversation_memory") or fields.get("conversation_memory") or {}
    flat["conversation_memory"] = memory if isinstance(memory, dict) else {}
    discovery = src.get("discovery_memory") or fields.get("discovery_memory") or {}
    flat["discovery_memory"] = discovery if isinstance(discovery, dict) else {}
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
    interpretation = interpret_user_message(text, state)
    semantic_updates = _updates_from_interpretation(
        interpretation.get("extracted_fields") or {},
        interpretation.get("intent") or "unknown",
        state,
        text,
    )
    if interpretation.get("confidence", 0) >= 0.65 or interpretation.get("stage_answered"):
        updates.update(semantic_updates)

    choice_updates = service_choice_update(norm) if (_is_pure_menu_number(norm) or norm.startswith("service_")) else {}
    if choice_updates:
        choice_service = choice_updates.get("service_interest") or ""
        if service and last_category and not detect_explicit_service_switch(text) and not _is_pure_menu_number(text):
            print(
                f"SALES_BRAIN_SERVICE_LOCKED service={service} "
                f"ignored_contextual_choice={choice_service} category={last_category} text={text[:160]!r}"
            )
        elif service and choice_service and choice_service != service and not detect_explicit_service_switch(text):
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

    if _has_any(norm, ["chatbot", "chat bot", "agente de ia", "agente ia"]) or (_has_any(norm, ["inteligencia artificial", "inteligência artificial"]) and _has_any(norm, ["criar", "chat", "bot", "atendimento", "vendas"])):
        updates.update(
            {
                "service_interest": "inteligencia_artificial",
                "intent": "inteligencia_artificial",
                "primary_track": "ia_no_negocio",
                "solution": "chatbot com IA",
                "process": "atendimento/vendas" if _has_any(norm, ["vendas", "vender", "comercial"]) else "atendimento",
                "related_needs": ["automacao_whatsapp", "vendas"],
                "funnel_stage": "qualificacao",
            }
        )

    if _has_any(norm, ["vendas", "vender", "vender mais", "mais vendas", "aumentar vendas"]):
        updates["objective"] = "vender mais"

    if _has_any(norm, ["falta de automacao", "falta da automacao", "sem automacao", "sem automação", "atendimento manual", "falta de automacao no atendimento", "falta da automacao de chatbot"]):
        updates["pain"] = "falta de automação no atendimento"
        updates["current_problem"] = updates.get("current_problem") or "falta de automação no atendimento"
        updates["current_tools"] = updates.get("current_tools") or "manual"
        updates["process"] = updates.get("process") or "atendimento/vendas"

    candidate_service = _service_candidate_from_text(norm)
    had_site_context = service == "site" or last_category == "site_scope"
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

    multi_answer = _multi_short_answer(norm)

    if last_category == "main_goal" and service == "branding":
        if multi_answer == "two":
            updates["main_goal"] = "posicionamento e conteúdo/redes sociais"
            updates["funnel_stage"] = "qualificacao"
            print(f"CONTEXTUAL_SHORT_ANSWER_PARSED category=main_goal service=branding value={updates['main_goal']!r} text={text[:160]!r}")
        elif multi_answer == "all":
            updates["main_goal"] = "posicionamento, conteúdo/redes sociais e identidade visual"
            updates["funnel_stage"] = "qualificacao"
            print(f"CONTEXTUAL_SHORT_ANSWER_PARSED category=main_goal service=branding value={updates['main_goal']!r} text={text[:160]!r}")
        elif _has_any(norm, ["conteudo", "redes", "social media"]):
            updates["main_goal"] = "conteúdo/redes sociais"
            updates["funnel_stage"] = "qualificacao"
        elif _has_any(norm, ["identidade", "visual"]):
            updates["main_goal"] = "identidade visual"
            updates["current_problem"] = updates.get("current_problem") or "clareza e consistência da marca"
            updates["funnel_stage"] = "qualificacao"
        elif "posicionamento" in norm:
            updates["main_goal"] = "posicionamento"
            updates["funnel_stage"] = "qualificacao"
        elif _has_any(norm, ["identidade da marca", "identidade visual", "identidade"]):
            updates["main_goal"] = "identidade visual"
            updates["current_problem"] = updates.get("current_problem") or "clareza e consistência da marca"
            updates["funnel_stage"] = "qualificacao"
        elif _has_any(norm, ["criar uma marca", "marca para divulgar", "divulgar meus produtos", "divulgar produtos"]):
            updates["main_goal"] = "criar marca para divulgar produtos"
            updates["desired_result"] = "apresentar melhor os produtos e gerar desejo"
            updates["current_problem"] = updates.get("current_problem") or "marca ainda precisa sustentar comunicação comercial"
            updates["funnel_stage"] = "qualificacao"
        elif _has_any(norm, ["crescimento da minha marca", "aumentar crescimento", "crescer minha marca", "crescimento de marca", "aumentar o crescimento"]):
            updates["main_goal"] = "crescimento de marca"
            updates["desired_result"] = "crescer com mais consistência"
            updates["current_problem"] = updates.get("current_problem") or "marca precisa crescer com consistência"
            updates["funnel_stage"] = "qualificacao"

    if last_category == "main_goal" and service == "trafego_pago" and multi_answer == "all":
        updates["main_goal"] = "gerar leads, vender no site e fortalecer marca"
        updates["funnel_stage"] = "qualificacao"
        print(f"CONTEXTUAL_SHORT_ANSWER_PARSED category=main_goal service=trafego_pago value={updates['main_goal']!r} text={text[:160]!r}")

    if service == "site" or last_category == "site_scope":
        if service == "site" and last_category == "site_scope" and _has_any(norm, ["whatsapp", "whats", "zap"]):
            updates["desired_result"] = "usar WhatsApp como canal de conversão"
            updates["current_problem"] = updates.get("current_problem") or "página precisa levar as pessoas para o WhatsApp"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=desired_result value='usar WhatsApp como canal de conversão' text={text[:160]!r}")
        if _has_any(norm, ["do zero", "nova", "novo", "nova pagina", "criar", "criar do zero", "comecar", "fazer uma nova"]):
            updates["site_scope"] = updates.get("site_scope") or "criar do zero"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=site_scope value='criar do zero' text={text[:160]!r}")
        elif _is_existing_site_scope(norm) and (had_site_context or normalize_text(norm) not in {"site", "meu site", "o site", "pagina", "minha pagina"}):
            updates["site_scope"] = updates.get("site_scope") or SITE_EXISTING_SCOPE
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=site_scope field=site_scope value={SITE_EXISTING_SCOPE!r} text={text[:160]!r}")

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
            updates["main_goal"] = "atendimento"
        elif _has_any(norm, ["processo", "operacao", "operação", "manual", "retrabalho"]):
            updates["main_goal"] = "processos internos"
        updates["funnel_stage"] = "qualificacao"
        print(f"SALES_BRAIN_CONTEXT_SIGNAL category={last_category} field=current_problem text={text[:160]!r}")
    elif not updates.get("main_goal") and _has_any(norm, ["vendas", "vender", "vender mais", "mais clientes", "leads", "gerar leads", "converter mais"]):
        updates["main_goal"] = "vendas/leads"
        updates["desired_result"] = "vender mais / gerar mais oportunidades"
        updates["funnel_stage"] = "qualificacao"
    elif not updates.get("main_goal") and _has_any(norm, ["tempo", "ganhar tempo", "responder rapido", "operacao", "automatizar processo"]):
        updates["main_goal"] = "operacao/tempo"
        updates["funnel_stage"] = "qualificacao"
    elif not updates.get("main_goal") and _has_any(norm, ["organizar", "crm", "funil", "acompanhar leads"]):
        updates["main_goal"] = "gestao/comercial"
        updates["funnel_stage"] = "qualificacao"
    elif not updates.get("main_goal") and (_has_any(norm, ["posicionamento", "conteudo"]) or (service == "branding" and "marca" in norm)):
        updates["main_goal"] = "marca/conteudo"
        updates["funnel_stage"] = "qualificacao"

    source = state.get("lead_source") or ""
    source_changed = False
    if last_category == "lead_source" and multi_answer == "all":
        source = "WhatsApp, Instagram e site"
        source_changed = True
        print(f"CONTEXTUAL_SHORT_ANSWER_PARSED category=lead_source value={source!r} text={text[:160]!r}")
    elif last_category == "lead_source" and _has_any(norm, ["whatsapp e instagram", "whats e insta", "zap e insta"]):
        source = "WhatsApp e Instagram"
        source_changed = True
    elif last_category == "lead_source" and _has_any(norm, ["whatsapp e site", "whats e site", "zap e site"]):
        source = "WhatsApp e site"
        source_changed = True
    elif last_category == "lead_source" and _has_any(norm, ["instagram e site", "insta e site"]):
        source = "Instagram e site"
        source_changed = True
    if "instagram" in norm or "insta" in norm:
        source = _append_source(source, "Instagram")
        source_changed = True
    if "whatsapp" in norm or "whats" in norm or "zap" in norm:
        source = _append_source(source, "WhatsApp")
        source_changed = True
    if "site" in norm and (last_category == "lead_source" or source):
        source = _append_source(source, "Site")
        source_changed = True
    if "indicacao" in norm:
        source = _append_source(source, "Indicação")
        source_changed = True
    if source and source_changed:
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

    if service == "branding" and last_category == "current_status":
        if _has_any(norm, ["do zero", "comecar do zero", "começar do zero", "nao temos", "ainda nao", "sem identidade"]):
            updates["current_status"] = "começar do zero"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=current_status field=current_status value='começar do zero' text={text[:160]!r}")
        elif _has_any(norm, ["ja temos", "já temos", "temos", "presenca ativa", "presença ativa", "ja existe", "redes ativas"]):
            updates["current_status"] = "já tem presença/identidade"
            print(f"SALES_BRAIN_CONTEXT_SIGNAL category=current_status field=current_status value='já tem presença/identidade' text={text[:160]!r}")

    if _has_deadline_urgency(norm):
        updates["urgency"] = "alta"
        updates["funnel_stage"] = "decisao"
        updates["lead_temperature"] = "hot"
        updates["meeting_suggested"] = True
        updates["briefing_ready"] = True
        updates["handoff"] = True
        updates["handoff_reason"] = "urgencia_com_prazo"
        updates["next_action"] = "handoff"
    elif _has_any(norm, ["esse mes", "este mes"]):
        updates["urgency"] = "media"
        updates["funnel_stage"] = "decisao"
    elif _has_any(norm, ["so vendo", "entendendo", "sem pressa"]):
        updates["urgency"] = "baixa"

    if _has_any(norm, ["tenho verba", "tenho orcamento", "tenho budget", "ja tenho verba"]):
        updates["budget_signal"] = "tem verba"
    elif _has_any(norm, ["sem verba", "baixo custo", "barato"]):
        updates["budget_signal"] = "sensível a preço"

    if _has_any(norm, ["voces conseguem", "vocês conseguem", "conseguem fazer", "conseguem me ajudar", "voces fazem", "vocês fazem"]):
        commercial_count = sum(1 for key in ["main_goal", "desired_result", "site_scope", "lead_source", "current_tools", "current_problem", "urgency", "budget_signal", "current_status"] if state.get(key) or updates.get(key))
        if (updates.get("service_interest") or service) and commercial_count >= 2:
            updates.update(
                {
                    "handoff": True,
                    "handoff_reason": "lead_perguntou_se_conseguimos",
                    "lead_temperature": "hot" if updates.get("urgency") == "alta" or state.get("urgency") == "alta" else "warm",
                    "meeting_suggested": True,
                    "briefing_ready": True,
                    "next_action": "handoff",
                    "funnel_stage": "decisao",
                }
            )

    locked_updates = _lock_known_field_updates(updates, state, text)
    locked_updates["conversation_memory"] = _memory_from_known_fields(state, locked_updates, text)
    locked_updates["discovery_memory"] = _discovery_from_known_fields(state, locked_updates, text)
    return locked_updates


def merge_state(old_state: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old_state or {})
    fields = dict(merged.get("lead_fields") or {})
    for key, value in (updates or {}).items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
        if key in FIELD_KEYS and key not in {"meeting_suggested", "briefing_ready", "handoff"}:
            fields[key] = value
    question = str((updates or {}).get("last_question_asked") or "").strip()
    if question:
        recent = merged.get("recent_bot_questions") or fields.get("recent_bot_questions") or []
        if not isinstance(recent, list):
            recent = []
        cleaned = [str(item).strip() for item in recent if str(item).strip()]
        if not cleaned or not is_duplicate_question(question, cleaned[-1]):
            cleaned.append(question)
        merged["recent_bot_questions"] = cleaned[-3:]
        fields["recent_bot_questions"] = cleaned[-3:]
    merged["lead_fields"] = fields
    return merged


def _progressive_automation_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    memory = _read_memory(state)
    if not memory.get("objetivo"):
        return {
            "category": "main_goal",
            "question": "O principal objetivo agora é vender mais, responder mais rápido ou organizar melhor o processo comercial?",
            "next_action": "ask_question",
        }
    if not memory.get("volume"):
        return {
            "category": "volume",
            "question": "Para dimensionar melhor, mais ou menos quantos leads ou conversas entram por semana?",
            "next_action": "ask_question",
        }
    if not memory.get("gargalo"):
        return {
            "category": "gargalo",
            "question": "Hoje o maior gargalo está na demora para responder, no acompanhamento dos leads ou na perda de oportunidades?",
            "next_action": "ask_question",
        }
    if not memory.get("crm"):
        return {
            "category": "crm",
            "question": "Vocês controlam esses leads em algum CRM ou ainda fica tudo no WhatsApp e na memória da equipe?",
            "next_action": "ask_question",
        }
    if not memory.get("tempo_resposta"):
        return {
            "category": "tempo_resposta",
            "question": "Quando um lead chama hoje, em média ele recebe retorno em minutos, horas ou só quando alguém consegue parar para responder?",
            "next_action": "ask_question",
        }
    if not memory.get("orcamento"):
        return {
            "category": "budget_signal",
            "question": "Vocês já têm uma faixa de investimento pensada para organizar essa operação?",
            "next_action": "ask_question",
        }
    return {
        "category": "offer_meeting",
        "question": "Já tenho uma leitura boa do cenário. Posso encaminhar isso para a Julia avaliar o próximo movimento com vocês?",
        "next_action": "offer_meeting",
    }


def _progressive_site_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    memory = _discovery_from_known_fields(state)["site"]
    if not memory.get("site_scope"):
        if (state.get("last_question_category") or "") == "site_scope":
            return {"category": "site_scope", "question": "Para eu não te prender numa pergunta travada: hoje existe alguma página no ar ou a ideia é construir uma nova base?", "next_action": "ask_question"}
        return {"category": "site_scope", "question": SITE_SCOPE_QUESTION, "next_action": "ask_question"}
    if memory.get("site_scope") == "criar do zero":
        if not memory.get("objetivo_pagina"):
            return {"category": "main_goal", "question": "Essa página precisa vender um serviço, captar leads ou apresentar melhor a marca?", "next_action": "ask_question"}
    elif not memory.get("problema_site"):
        return {"category": "current_problem", "question": SITE_PROBLEM_QUESTION, "next_action": "ask_question"}
    if not memory.get("objetivo_pagina"):
        return {"category": "main_goal", "question": "O foco dessa página é gerar leads, vender mais ou apresentar melhor a marca?", "next_action": "ask_question"}
    if not memory.get("publico"):
        return {"category": "publico", "question": "Essa página fala mais com clientes finais, empresas ou um público mais específico?", "next_action": "ask_question"}
    if not memory.get("prazo"):
        return {"category": "urgency", "question": "Você tem alguma data ou campanha em mente para colocar essa página no ar?", "next_action": "ask_question"}
    return {"category": "offer_meeting", "question": "Já tenho uma boa leitura da página. Posso encaminhar para a Julia avaliar o próximo movimento?", "next_action": "offer_meeting"}


def _progressive_ai_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    memory = _discovery_from_known_fields(state)["inteligencia_artificial"]
    if state.get("solution") == "chatbot com IA" and not (state.get("objective") or state.get("main_goal")):
        return {
            "category": "main_goal",
            "question": "Então o caminho é criar um agente de IA para atendimento. Esse chatbot precisa mais qualificar leads, responder dúvidas ou conduzir vendas?",
            "next_action": "ask_question",
        }
    if state.get("solution") == "chatbot com IA" and (state.get("objective") or state.get("main_goal")) and not (state.get("pain") or state.get("current_problem")):
        return {
            "category": "current_problem",
            "question": "Boa. Então ele precisa atuar no comercial, não só no suporte. Hoje a maior perda acontece por demora na resposta ou por falta de acompanhamento dos contatos?",
            "next_action": "ask_question",
        }
    if not memory.get("processo"):
        return {"category": "main_goal", "question": "Qual processo você imagina melhorar com IA: atendimento, vendas, conteúdo ou operação interna?", "next_action": "ask_question"}
    if not memory.get("dor_operacional"):
        return {"category": "current_problem", "question": "Hoje qual parte desse processo mais trava: volume, tempo de resposta, retrabalho ou falta de padrão?", "next_action": "ask_question"}
    if not memory.get("ferramenta_atual"):
        return {"category": "current_tools", "question": "Hoje esse processo acontece manualmente ou já passa por alguma ferramenta?", "next_action": "ask_question"}
    if not memory.get("volume_tarefa"):
        return {"category": "volume_tarefa", "question": "Esse processo acontece poucas vezes por semana ou em alto volume todos os dias?", "next_action": "ask_question"}
    if not memory.get("orcamento"):
        return {"category": "budget_signal", "question": "Vocês já têm uma faixa de investimento pensada para automatizar isso?", "next_action": "ask_question"}
    return {"category": "offer_meeting", "question": "Já dá para desenhar uma hipótese de IA com impacto. Posso encaminhar para a Julia avaliar com vocês?", "next_action": "offer_meeting"}


def _progressive_traffic_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    memory = _discovery_from_known_fields(state)["trafego_pago"]
    if not memory.get("estrutura_atual"):
        return {"category": "current_status", "question": "Hoje vocês já anunciam ou querem começar do zero?", "next_action": "ask_question"}
    if not memory.get("objetivo_campanha"):
        return {"category": "main_goal", "question": "O foco da campanha é gerar leads, vender no site ou fortalecer a marca?", "next_action": "ask_question"}
    if not memory.get("oferta"):
        return {"category": "oferta", "question": "Qual oferta, produto ou serviço você quer colocar no centro dessa campanha?", "next_action": "ask_question"}
    if not memory.get("verba"):
        return {"category": "budget_signal", "question": "Vocês já têm uma verba mensal pensada para mídia?", "next_action": "ask_question"}
    if not memory.get("problema_performance") and memory.get("estrutura_atual") == "já anuncia":
        return {"category": "problema_performance", "question": "Hoje o ponto que mais incomoda é custo, conversão, volume de leads ou qualidade das oportunidades?", "next_action": "ask_question"}
    return {"category": "offer_meeting", "question": "Já tenho contexto para avaliar mídia com mais responsabilidade. Posso encaminhar para a Julia?", "next_action": "offer_meeting"}


def _progressive_branding_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    memory = _discovery_from_known_fields(state)["branding"]
    objective = normalize_text(memory.get("objetivo_comunicacao") or "")
    focus = normalize_text(memory.get("foco_marca") or "")
    if not (memory.get("foco_marca") or memory.get("objetivo_comunicacao")):
        if memory.get("canal_principal") == "Instagram":
            return {"category": "dificuldade_atual", "question": "Hoje o maior desafio está em atrair pessoas certas, transformar interesse em conversa ou manter constância de conteúdo?", "next_action": "ask_question"}
        return {"category": "main_goal", "question": "Você quer fortalecer posicionamento, identidade visual ou conteúdo para redes?", "next_action": "ask_question"}
    if "divulgar produtos" in objective and memory.get("produto_servico") == "produtos":
        return {"category": "produto_servico", "question": "Esses produtos já são vendidos hoje ou ainda estão em fase de lançamento?", "next_action": "ask_question"}
    if "crescimento" in objective and not memory.get("canal_principal"):
        return {"category": "canal_principal", "question": "Hoje vocês já publicam com frequência?", "next_action": "ask_question"}
    if ("identidade" in focus or "construcao" in focus or "construção" in focus) and not memory.get("estagio_marca"):
        return {"category": "estagio_marca", "question": "Hoje essa marca já tem nome, identidade visual e redes ativas ou ainda está sendo estruturada do zero?", "next_action": "ask_question"}
    if not memory.get("produto_servico"):
        return {"category": "produto_servico", "question": "O que essa marca vende ou quer apresentar melhor: produtos, serviços ou uma nova oferta?", "next_action": "ask_question"}
    if not memory.get("canal_principal"):
        return {"category": "canal_principal", "question": "Hoje o principal canal de comunicação é Instagram, WhatsApp, site ou outro ponto de contato?", "next_action": "ask_question"}
    if not memory.get("dificuldade_atual"):
        return {"category": "dificuldade_atual", "question": "Você quer começar mais pela construção da marca, pela organização do conteúdo ou por uma estratégia para gerar demanda?", "next_action": "ask_question"}
    if not memory.get("orcamento"):
        return {"category": "budget_signal", "question": "Vocês já têm uma faixa de investimento pensada para essa frente de marca e comunicação?", "next_action": "ask_question"}
    return {"category": "offer_meeting", "question": "Já tenho uma leitura consistente da marca. Posso encaminhar para a Julia avaliar o próximo movimento?", "next_action": "offer_meeting"}


def get_next_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    service = state.get("service_interest") or state.get("selected_service") or ""
    offer = {
        "category": "offer_meeting",
        "question": "Perfeito, já tenho um bom contexto. Posso encaminhar um resumo para a Julia e agilizar o próximo passo?",
        "next_action": "offer_meeting",
    }
    if state.get("handoff") or service == "humano":
        return {"category": "handoff", "question": "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma.", "next_action": "handoff"}
    if should_handoff_now(state, []):
        return {"category": "handoff", "question": "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma.", "next_action": "handoff"}
    if service == "site":
        return _progressive_site_question(state)
    if service == "automacao_whatsapp":
        if not state.get("lead_source"):
            return {"category": "lead_source", "question": "Por qual canal você mais recebe oportunidades comerciais hoje?", "next_action": "ask_question"}
        if not (state.get("current_tools") or state.get("current_problem")):
            return {"category": "current_tools", "question": "O atendimento hoje depende muito de resposta manual ou já tem algum fluxo automatizado?", "next_action": "ask_question"}
        return _progressive_automation_question(state)
    if service == "inteligencia_artificial":
        return _progressive_ai_question(state)
    if service == "trafego_pago":
        return _progressive_traffic_question(state)
    if service == "branding":
        return _progressive_branding_question(state)
    return {
        "category": "service_interest",
        "question": "Vou seguir por uma leitura mais ampla para não te prender em pergunta solta. Hoje você busca mais clareza estratégica, melhoria de comunicação ou automação do atendimento?",
        "next_action": "ask_question",
    }


def question_category(text: str) -> str:
    norm = normalize_text(text)
    if (
        "prioridade e pagina" in norm
        or ("pagina" in norm and "whatsapp" in norm and "marca" in norm)
        or ("procura" in norm and "automacao" in norm and "branding" in norm)
        or ("clareza estrategica" in norm and "automacao do atendimento" in norm)
    ):
        return "service_interest"
    if "pagina nova" in norm or "melhorar uma pagina" in norm:
        return "site_scope"
    if (
        "maior incomodo" in norm
        or ("visual" in norm and "conversao" in norm)
        or ("velocidade" in norm and "clareza" in norm)
        or ("maior desafio" in norm and "constancia de conteudo" in norm)
        or "principal ponto que voce quer resolver" in norm
        or "estrategia para gerar demanda" in norm
    ):
        return "current_problem"
    if "vendas/leads" in norm or "vender mais" in norm or "gerar leads" in norm or "foco e gerar" in norm:
        return "main_goal"
    if (
        "oportunidades comerciais" in norm
        or ("whatsapp" in norm and ("chegam" in norm or "chega" in norm or "por onde" in norm or ("instagram" in norm and "site" in norm)))
    ):
        return "lead_source"
    if "manual" in norm or "fluxo automatizado" in norm or "ferramenta" in norm or "crm" in norm or "ja anunciam" in norm:
        return "current_tools" if "anunciam" not in norm else "current_status"
    if "quantos leads" in norm or "quantas conversas" in norm or "entram por semana" in norm:
        return "volume"
    if "alto volume todos os dias" in norm or "poucas vezes por semana" in norm:
        return "volume_tarefa"
    if "maior gargalo" in norm or "perda de oportunidades" in norm or "acompanhamento dos leads" in norm:
        return "gargalo"
    if "algum crm" in norm or "fica tudo no whatsapp" in norm:
        return "crm"
    if "recebe retorno" in norm or "minutos horas" in norm or "tempo de resposta" in norm:
        return "tempo_resposta"
    if "nome identidade visual e redes ativas" in norm or "estruturada do zero" in norm:
        return "estagio_marca"
    if "produtos ja sao vendidos" in norm or "fase de lancamento" in norm or "essa marca vende" in norm:
        return "produto_servico"
    if "principal canal de comunicacao" in norm or "publicam com frequencia" in norm:
        return "canal_principal"
    if "qual oferta produto ou servico" in norm:
        return "oferta"
    if "clientes finais empresas" in norm:
        return "publico"
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
    memory = _read_memory(state)
    discovery = _read_discovery_memory(state)
    if category == "current_tools":
        return bool(state.get("current_tools"))
    if category == "current_status":
        return bool(state.get("current_status") or state.get("current_tools"))
    if category == "lead_source":
        return bool(state.get("lead_source"))
    if category == "site_scope":
        return bool(state.get("site_scope"))
    if category == "main_goal":
        return bool(state.get("main_goal"))
    if category == "offer_meeting":
        return False
    if category in {"volume", "gargalo", "crm", "tempo_resposta"}:
        return bool(memory.get(category))
    discovery_map = {
        "publico": ("site", "publico"),
        "volume_tarefa": ("inteligencia_artificial", "volume_tarefa"),
        "oferta": ("trafego_pago", "oferta"),
        "problema_performance": ("trafego_pago", "problema_performance"),
        "estagio_marca": ("branding", "estagio_marca"),
        "produto_servico": ("branding", "produto_servico"),
        "canal_principal": ("branding", "canal_principal"),
        "dificuldade_atual": ("branding", "dificuldade_atual"),
    }
    if category in discovery_map:
        service, key = discovery_map[category]
        return bool((discovery.get(service) or {}).get(key))
    return bool(state.get(category))


def _non_repeating_recovery_question(state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    service = state.get("service_interest") or state.get("selected_service") or ""
    last_category = state.get("last_question_category") or question_category(state.get("last_question_asked") or "")
    if service == "site":
        if last_category == "site_scope" and not state.get("current_problem"):
            return {"category": "current_problem", "question": "Me conta em uma frase o que mais precisa melhorar no site hoje?", "next_action": "ask_question"}
        if not state.get("current_problem"):
            return {"category": "current_problem", "question": SITE_PROBLEM_QUESTION, "next_action": "ask_question"}
    if service == "branding":
        return _progressive_branding_question(state)
    return {"category": "current_problem", "question": "Qual gargalo comercial está mais claro para você hoje?", "next_action": "ask_question"}


def _matches_recent_question(reply: str, state: Dict[str, Any]) -> bool:
    recent = flatten_state(state).get("recent_bot_questions") or []
    return any(is_duplicate_question(reply, question) for question in recent[-3:])


ONE_TIME_QUESTIONS = [
    "qual gargalo comercial esta mais claro para voce hoje",
    "por qual canal voce mais recebe oportunidades comerciais hoje",
    "o atendimento hoje depende muito de resposta manual",
    "ja tem algum fluxo automatizado",
]


def _is_one_time_question_repeated(reply: str, state: Dict[str, Any]) -> bool:
    norm = normalize_text(reply)
    if not any(item in norm for item in ONE_TIME_QUESTIONS):
        return False
    recent = flatten_state(state).get("recent_bot_questions") or []
    return any(any(item in normalize_text(question) for item in ONE_TIME_QUESTIONS) for question in recent)


def validate_reply(reply: str, state: Dict[str, Any]) -> Dict[str, Any]:
    state = flatten_state(state)
    next_q = get_next_question(state)
    category = question_category(reply)
    blocked = False
    reason = ""
    if is_duplicate_question(reply, state.get("last_question_asked") or "") or _matches_recent_question(reply, state) or _is_one_time_question_repeated(reply, state):
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
        if should_handoff_now(state, []):
            return {
                "category": "handoff",
                "question": "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma.",
                "reply": "Perfeito. Já tenho contexto suficiente para direcionar você da melhor forma.",
                "next_action": "handoff",
                "blocked": True,
                "reason": reason,
            }
        if reason == "forbidden_generic_reply" and state.get("service_interest") == "site":
            next_q = _non_repeating_recovery_question(state)
        if is_duplicate_question(next_q.get("question") or "", state.get("last_question_asked") or "") or _matches_recent_question(next_q.get("question") or "", state):
            next_q = _non_repeating_recovery_question(state)
        return {**next_q, "reply": next_q["question"], "blocked": True, "reason": reason}
    return {**next_q, "reply": reply, "blocked": False, "reason": ""}


def validate_final_reply(reply: str, state: Dict[str, Any]) -> Dict[str, Any]:
    return validate_reply(reply, state)


def build_contextual_reply(
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    extracted_signals: Dict[str, Any],
    next_question: Dict[str, Any],
) -> str:
    before = flatten_state(state_before or {})
    after = flatten_state(state_after or {})
    signals = extracted_signals or {}
    question = (next_question or {}).get("question") or ""
    confirmation = ""

    if after.get("solution") == "chatbot com IA" and signals.get("pain"):
        confirmation = "Entendi. Já existe uma dor clara: o atendimento ainda depende muito do manual e isso trava vendas."
    elif after.get("solution") == "chatbot com IA" and (signals.get("objective") or signals.get("main_goal") == "vendas/leads"):
        confirmation = "Boa. Então ele precisa atuar no comercial, não só no suporte."
    elif signals.get("solution") == "chatbot com IA":
        confirmation = "Então o caminho é criar um agente de IA para atendimento."

    lead_source = signals.get("lead_source")
    if not confirmation and lead_source:
        source_norm = normalize_text(str(lead_source))
        if source_norm == "whatsapp":
            confirmation = "Faz sentido. Então o foco é melhorar o atendimento e a entrada de leads pelo WhatsApp."
        elif "instagram" in source_norm and after.get("service_interest") == "branding":
            confirmation = "Então o ponto de entrada é o Instagram."
        else:
            confirmation = f"Boa, vou considerar {lead_source} como principal ponto de entrada."
    elif signals.get("current_tools") == "manual":
        confirmation = "Aí a automação pode ajudar bastante a organizar e acelerar o retorno."
    elif signals.get("site_scope") in {SITE_EXISTING_SCOPE, "melhorar existente"}:
        confirmation = "Então o foco é melhorar uma estrutura que já existe."
    elif signals.get("site_scope") == "criar do zero":
        confirmation = "Legal. Então estamos falando de criar uma página nova do zero."
    elif signals.get("current_status") == "começar do zero":
        confirmation = "Ótimo. Então a ideia é começar a mídia paga do jeito certo."
    elif signals.get("current_status") == "já anuncia":
        confirmation = "Boa. Então vocês já têm alguma experiência com anúncios."
    elif signals.get("urgency") == "alta":
        confirmation = "Esse prazo pede um encaminhamento mais ágil."
    elif signals.get("main_goal") == "vendas/leads":
        confirmation = "Faz sentido, então o foco é gerar mais oportunidades."
    elif after.get("service_interest") == "branding" and signals.get("main_goal") == "identidade visual":
        confirmation = "Então o foco é dar mais clareza e consistência para a marca."
    elif after.get("service_interest") == "branding" and signals.get("main_goal") == "criar marca para divulgar produtos":
        confirmation = "Boa. Então existe uma intenção comercial por trás da marca: apresentar melhor os produtos e gerar desejo."
    elif after.get("service_interest") == "branding" and signals.get("main_goal") == "crescimento de marca":
        confirmation = "Faz sentido. Para crescer com consistência, precisamos entender se o desafio está mais em posicionamento, conteúdo ou aquisição."
    elif after.get("service_interest") == "branding" and signals.get("main_goal") == "posicionamento e conteúdo/redes sociais":
        confirmation = "Então vamos considerar posicionamento e conteúdo como frentes conectadas."
    elif after.get("service_interest") == "branding" and signals.get("main_goal"):
        confirmation = "Então o foco é construir uma marca com mais clareza e força comercial."
    elif signals.get("main_goal") == "gerar leads, vender no site e fortalecer marca":
        confirmation = "Então o objetivo é cobrir os três pontos com uma estratégia integrada."
    elif signals.get("main_goal") == "atendimento" or normalize_text(str(signals.get("current_problem") or "")) == "atendimento":
        confirmation = "Então faz sentido pensar em IA para acelerar o atendimento e não deixar lead esfriar."
    elif signals.get("main_goal"):
        confirmation = "Vou considerar esse foco como ponto de partida."
    elif signals.get("current_problem") and after.get("service_interest") == "inteligencia_artificial":
        confirmation = "Boa. Esse é um bom ponto para a IA ajudar."
    elif after.get("service_interest") == "site" and not before.get("service_interest"):
        confirmation = "Então o ponto central parece ser a estrutura digital."
    elif after.get("service_interest") == "automacao_whatsapp" and not before.get("service_interest"):
        confirmation = "Faz sentido. Vou olhar isso pela frente de atendimento e relacionamento."
    elif after.get("service_interest") == "branding" and not before.get("service_interest"):
        confirmation = "Boa. Vou puxar isso para comunicação e posicionamento."
    elif after.get("service_interest") == "trafego_pago" and not before.get("service_interest"):
        confirmation = "Legal. Vou olhar isso pela frente de aquisição."

    if not confirmation:
        return question
    if not question:
        return confirmation
    if normalize_text(confirmation) in normalize_text(question):
        return question
    return f"{confirmation} {question}".strip()


def should_handoff(state: Dict[str, Any], message: str) -> bool:
    updates = extract_signal_from_message(message, state)
    return bool(updates.get("handoff") or flatten_state(state).get("handoff"))


def should_handoff_now(conversation_memory: Dict[str, Any] | None, messages: list | None = None) -> bool:
    state = flatten_state(conversation_memory or {})
    inbound_texts = _message_texts(messages, direction="in") or _message_texts(messages)
    joined = normalize_text(" | ".join(inbound_texts))

    if bool(state.get("handoff")) or _has_any(joined, ["humano", "atendente", "falar com alguem", "falar com alguém", "falar com a equipe", "julia", "pessoa"]):
        return True

    solution = state.get("solution")
    service = state.get("primary_track") or state.get("service_interest") or state.get("intent")
    if not service and _has_any(joined, ["chatbot", "chat bot", "inteligencia artificial", "inteligência artificial", "agente de ia"]):
        service = "ia_no_negocio"

    objective = state.get("objective") or state.get("desired_result") or state.get("main_goal")
    if not objective and _has_any(joined, ["vendas", "vender", "vender mais", "mais vendas", "gerar leads"]):
        objective = "vender mais"

    pain = state.get("pain") or state.get("current_problem")
    if normalize_text(pain) in {"atendimento", "vendas", "processo manual"} and not solution:
        pain = ""
    if not pain and _has_any(joined, ["falta de automacao", "falta da automacao", "sem automacao", "sem automação", "manual", "demora", "perda de leads"]):
        pain = "falta de automação no atendimento"

    process = state.get("process") or state.get("lead_source") or state.get("current_tools")
    if not process and _has_any(joined, ["atendimento", "whatsapp", "vendas", "comercial", "chatbot"]):
        process = "atendimento/vendas"

    urgency = state.get("urgency")
    if not urgency and _has_any(joined, ["urgente", "para ontem", "pra ontem", "o quanto antes", "ate dia", "até dia"]):
        urgency = "alta"

    score = sum(bool(item) for item in [service, objective, pain, process, urgency])
    return score >= 3 and bool(urgency or (objective and pain and (process or solution)))


def _commercial_field_count(state: Dict[str, Any]) -> int:
    state = flatten_state(state)
    keys = ["main_goal", "desired_result", "site_scope", "lead_source", "current_tools", "current_problem", "urgency", "budget_signal", "current_status"]
    return sum(1 for key in keys if state.get(key))


def should_offer_meeting(state: Dict[str, Any]) -> bool:
    state = flatten_state(state)
    if should_handoff_now(state, []):
        return True
    if has_enough_briefing_for_handoff(state):
        return True
    if get_next_question(state).get("next_action") == "offer_meeting":
        return True
    if state.get("urgency") == "alta" and state.get("service_interest") and _commercial_field_count(state) >= 2:
        return True
    if state.get("budget_signal") == "tem verba" and state.get("service_interest") and _commercial_field_count(state) >= 2:
        return True
    return False


def has_enough_briefing_for_handoff(state: Dict[str, Any]) -> bool:
    state = flatten_state(state)
    service = state.get("service_interest")
    if not service or not state.get("main_goal"):
        print(f"BRIEFING_COMPLETENESS_CHECK service={service or '-'} enough=false reason=missing_service_or_goal")
        return False
    has_context = bool(state.get("current_problem") or state.get("current_status") or state.get("current_tools") or state.get("site_scope"))
    has_decision_signal = bool(state.get("urgency") or state.get("budget_signal") or state.get("handoff_reason") == "lead_perguntou_se_conseguimos")
    enough = bool(has_context and has_decision_signal)
    print(
        "BRIEFING_COMPLETENESS_CHECK "
        f"service={service} enough={str(enough).lower()} has_context={str(has_context).lower()} "
        f"has_decision_signal={str(has_decision_signal).lower()}"
    )
    return enough


def _as_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join([_as_text(item) for item in value if _as_text(item)])
    return str(value or "").strip()


def _service_label(value: Any) -> str:
    raw = _as_text(value)
    return SERVICE_LABELS.get(raw, raw.replace("_", " "))


def _message_texts(messages: list | None, direction: str = "") -> List[str]:
    texts: List[str] = []
    for item in messages or []:
        if isinstance(item, dict):
            if direction and str(item.get("direction") or "").strip() != direction:
                continue
            text = str(item.get("text") or item.get("body") or item.get("message") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            texts.append(text)
    return texts


def _contains_any_text(texts: List[str], needles: List[str]) -> bool:
    joined = normalize_text(" | ".join(texts))
    return any(needle in joined for needle in needles)


def _safe_analysis_text(value: Any) -> str:
    text = _as_text(value)
    norm = normalize_text(text)
    if not text:
        return ""
    if norm in {"outro", "humano", "indefinido"}:
        return ""
    if norm in RAW_LOW_SIGNAL_PHRASES or any(phrase in norm for phrase in RAW_LOW_SIGNAL_PHRASES):
        return ""
    return text


def _dedupe_texts(values: List[Any], limit: int = 6) -> List[str]:
    items: List[str] = []
    seen = set()
    for value in values:
        text = _safe_analysis_text(value)
        if not text:
            continue
        key = normalize_text(text)
        if key and key not in seen:
            seen.add(key)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _infer_related_needs(state: Dict[str, Any], messages: list | None) -> List[str]:
    state = flatten_state(state)
    inbound = _message_texts(messages, direction="in") or _message_texts(messages)
    related: List[str] = []
    joined = normalize_text(" | ".join(inbound))
    checks = [
        ("automacao_whatsapp", ["whatsapp", "whats", "zap", "atendimento", "crm", "lead"]),
        ("site", ["site", "landing", "pagina", "ecommerce", "loja virtual"]),
        ("trafego_pago", ["campanha", "trafego", "tráfego", "anuncio", "anúncio", "ads", "performance"]),
        ("branding", ["comunicacao", "comunicação", "posicionamento", "marca", "conteudo", "conteúdo", "instagram"]),
        ("inteligencia_artificial", [" ia ", "inteligencia artificial", "inteligência artificial", "chatbot", "automacao"]),
    ]
    primary = state.get("primary_track") or state.get("service_interest") or state.get("intent")
    for service, needles in checks:
        if service != primary and any(needle in joined for needle in needles):
            related.append(service)
    existing = state.get("related_needs")
    if isinstance(existing, list):
        related.extend([str(item) for item in existing])
    return _dedupe_texts(related, limit=5)


def build_internal_briefing(conversation_memory: Dict[str, Any] | None, messages: list | None) -> Dict[str, Any]:
    state = flatten_state(conversation_memory or {})
    inbound_texts = _message_texts(messages, direction="in") or _message_texts(messages)
    all_texts = _message_texts(messages)
    primary_track = state.get("primary_track") or state.get("service_interest") or state.get("intent") or ""
    solution = state.get("solution")
    objective = state.get("objective")
    pain = state.get("pain")
    process = state.get("process")
    joined = normalize_text(" | ".join(inbound_texts))
    if solution == "chatbot com IA" or _has_any(joined, ["chatbot", "chat bot", "agente de ia"]):
        primary_track = "ia_no_negocio"
        solution = solution or "chatbot com IA"
        process = process or "atendimento/vendas"
        if not objective and _has_any(joined, ["vendas", "vender", "vender mais", "mais vendas"]):
            objective = "vender mais"
        if not pain and _has_any(joined, ["falta de automacao", "falta da automacao", "sem automacao", "sem automação", "manual"]):
            pain = "falta de automação no atendimento"
    if normalize_text(primary_track) in {"outro", "humano"}:
        primary_track = "ia_no_negocio" if solution == "chatbot com IA" else ""
    related_needs = _infer_related_needs(state, messages)
    channel = state.get("lead_source") or ("WhatsApp" if inbound_texts else "")
    business = state.get("business_type") or state.get("business_name")
    goal = objective or state.get("desired_result") or state.get("main_goal")
    problem = pain or state.get("current_problem") or state.get("current_status")
    tools = process or state.get("current_tools")
    urgency = state.get("urgency")
    budget = state.get("budget_signal")
    asks_for_all = _contains_any_text(inbound_texts, ["tudo", "todas as frentes", "todas as frente", "me ajudem", "me ajuda"])
    high_urgency = urgency == "alta" or _contains_any_text(inbound_texts, ["para ontem", "urgente", "o quanto antes", "ate dia", "até dia"])
    multi_front = bool(len(related_needs) >= 2 or asks_for_all)

    if asks_for_all and not problem:
        problem = "necessidade de organizar múltiplas frentes da operação digital"
    if high_urgency and not urgency:
        urgency = "alta"
    if multi_front and not primary_track:
        primary_track = "consultoria"

    front_label = _service_label(primary_track) if primary_track else "demanda integrada"
    related_labels = [_service_label(item) for item in related_needs if item and item != primary_track]
    business_phrase = _safe_analysis_text(business)
    goal_phrase = _safe_analysis_text(goal) or ("vender mais" if solution == "chatbot com IA" else "avançar o resultado comercial")
    problem_phrase = _safe_analysis_text(problem) or "priorização e diagnóstico das principais travas"
    channel_phrase = _safe_analysis_text(channel) or "WhatsApp"
    tools_phrase = _safe_analysis_text(tools)

    if solution == "chatbot com IA":
        moment = (
            "Lead busca criar um chatbot com inteligência artificial para automatizar o atendimento e apoiar vendas. "
            f"A dor principal está na {problem_phrase}."
        )
    else:
        moment_parts = [
            f"Lead com frente principal em {front_label}",
            f"canal de entrada {channel_phrase}",
        ]
        if business_phrase:
            moment_parts.append(f"negócio/produto: {business_phrase}")
        if goal_phrase:
            moment_parts.append(f"objetivo comercial: {goal_phrase}")
        if related_labels:
            moment_parts.append(f"frentes secundárias percebidas: {', '.join(related_labels)}")
        moment = ". ".join(moment_parts) + "."

    if solution == "chatbot com IA":
        strategic = "Existe uma oportunidade clara de estruturar um atendimento automatizado com IA para qualificar contatos, reduzir operação manual e aumentar conversão."
    elif multi_front:
        strategic = (
            "A demanda deve ser tratada como integrada, não como pedido isolado. "
            "O lead demonstra necessidade de organizar aquisição, comunicação, estrutura digital e conversão, "
            "com prioridade comercial para entender onde a operação está travando."
        )
    else:
        strategic = (
            f"A dor principal aparece em {problem_phrase}. "
            f"A conversa deve conectar essa trava ao objetivo de {goal_phrase}, validando impacto e prioridade antes de propor escopo."
        )
    if high_urgency:
        strategic += " O lead demonstra urgência alta e busca apoio para priorizar os próximos movimentos."

    opportunity_needs = related_labels or ([_service_label(primary_track)] if primary_track else [])
    opportunity = "Atuação combinada em "
    if solution == "chatbot com IA":
        opportunity += "agente de IA, automação de WhatsApp e estruturação do fluxo comercial."
    elif multi_front:
        opportunity += "automação de WhatsApp, revisão da jornada comercial, comunicação da oferta e organização de campanhas."
    elif opportunity_needs:
        opportunity += f"{', '.join(opportunity_needs)}, conectando diagnóstico comercial com execução prática."
    else:
        opportunity += "diagnóstico comercial, priorização de canais e clareza da oferta."

    maturity_bits = []
    if goal:
        maturity_bits.append("objetivo comercial declarado")
    if problem:
        maturity_bits.append("dor operacional/comercial citada")
    if channel or tools:
        maturity_bits.append("canais ou ferramentas já mapeados")
    if high_urgency:
        maturity_bits.append("urgência alta")
    maturity = ", ".join(maturity_bits) if maturity_bits else "inicial, com abertura para diagnóstico"

    pain_points = _dedupe_texts(
        [
            problem_phrase,
            "operação digital com múltiplas frentes a organizar" if multi_front else "",
            f"uso atual de {tools_phrase}" if tools_phrase else "",
        ],
        limit=5,
    )
    goals = _dedupe_texts([goal_phrase], limit=3)
    questions = [
        "Qual é o volume atual de leads/conversas?",
        "Qual gargalo mais afeta conversão hoje?",
        "Qual prioridade comercial precisa destravar primeiro?",
    ]
    next_step = (
        "Julia/Kleber devem assumir com diagnóstico curto, começando por volume de leads, "
        "principal gargalo de conversão e prioridade comercial."
    )

    return {
        "summary": moment,
        "moment": moment,
        "strategic_reading": strategic,
        "opportunity": opportunity,
        "service_interest": primary_track,
        "primary_track": primary_track,
        "related_needs": related_needs,
        "entry_channel": channel_phrase,
        "business": business_phrase,
        "commercial_goal": goal_phrase,
        "solution": solution,
        "objective": objective or goal_phrase,
        "pain": pain or problem_phrase,
        "process": process or tools_phrase,
        "pain_points": pain_points,
        "goals": goals,
        "urgency": urgency or ("alta" if high_urgency else None),
        "maturity": maturity,
        "budget_signal": budget,
        "recommended_solution": primary_track or ("demanda integrada" if multi_front else ""),
        "questions_to_julia": questions,
        "suggested_next_step": next_step,
        "source_message_count": len(all_texts),
    }


def build_briefing(state: Dict[str, Any], recent_messages: list) -> Dict[str, Any]:
    return build_internal_briefing(state, recent_messages)
