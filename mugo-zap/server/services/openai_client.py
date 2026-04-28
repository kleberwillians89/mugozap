import os
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

OPENAI_API_KEY = (
    os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_KEY")
    or ""
).strip()

OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT") or "12")
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "atendimento_mugo.txt"
_PROMPT_CACHE = ""


def _ai_log(event: str, **fields: Any) -> None:
    safe_fields = []
    for key, value in fields.items():
        if key in {"prompt", "messages", "api_key", "token"}:
            continue
        safe_fields.append(f"{key}={str(value)[:220]}")
    print(f"OPENAI_CLIENT:{event} " + " ".join(safe_fields))
    if event == "request":
        print("AI_CALL_START " + " ".join(safe_fields))
    if event == "response":
        print("AI_CALL_RESULT " + " ".join(safe_fields))


def load_mugo_prompt() -> str:
    global _PROMPT_CACHE

    if _PROMPT_CACHE:
        return _PROMPT_CACHE

    try:
        _PROMPT_CACHE = PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        _PROMPT_CACHE = (
            "Você é a MugôZap, assistente da Mugô. Responda de forma curta, humana "
            "e sempre em JSON válido."
        )

    return _PROMPT_CACHE


def _fallback(user_message: str) -> Dict[str, Any]:
    msg = (user_message or "").strip()
    score = _score_from_text(msg)
    intent = _detect_theme(msg)
    temperature = _derive_temp(score)
    handoff = score >= 70
    meeting_suggested = score >= 70 and intent != "humano"
    next_action = "handoff" if handoff and intent == "humano" else ("offer_meeting" if meeting_suggested else "ask_question")

    return {
        "reply": _fallback_reply(msg, intent, score),
        "intent": intent,
        "next_action": next_action,
        "question_key": "none",
        "handoff": handoff and intent == "humano",
        "handoff_reason": "lead_com_intencao_comercial" if handoff else None,
        "handoff_summary": msg[:220],
        "next_intent": "next",
        "lead_score": score,
        "lead_temperature": temperature,
        "lead_theme": intent,
        "meeting_suggested": meeting_suggested,
        "briefing_ready": handoff,
        "suggested_tags": _tags_from_intent(intent, score, handoff),
        "lead_fields": _default_lead_fields(msg, intent),
        "briefing": _default_briefing(msg, intent),
        "follow_up": {"needed": False, "when": None, "message": None},
        "memory_summary": msg[:220],
        "memory_theme": intent,
        "memory_goal": msg[:180],
}


def _fallback_reply(msg: str, intent: str, score: int) -> str:
    lower = (msg or "").lower()
    if any(k in lower for k in ["preço", "preco", "valor", "orçamento", "orcamento", "quanto custa"]):
        return (
            "Depende do escopo. Pra eu te direcionar melhor: você quer resolver primeiro "
            "site/landing, automação no WhatsApp ou os dois juntos?"
        )
    if intent == "humano":
        return "Perfeito, vou encaminhar para alguém da equipe da Mugô continuar com você."
    if score >= 70:
        return "Entendi. Parece um caso com prioridade. Qual resultado você precisa alcançar primeiro?"
    return "Perfeito. Pra eu te direcionar melhor: isso impacta mais vendas/leads ou operação/tempo?"


def _score_from_text(t: str) -> int:
    t = (t or "").lower()
    score = 0

    if any(k in t for k in ["orçamento", "orcamento", "preço", "preco", "valor", "proposta", "quanto custa", "valores"]):
        score += 35

    if any(k in t for k in ["prazo", "urgente", "hoje", "amanhã", "amanha", "essa semana", "começar essa semana"]):
        score += 25

    if any(k in t for k in ["fechar", "contrato", "assinar", "começar", "comecar"]):
        score += 25

    if any(k in t for k in ["site", "landing page", "e-commerce", "loja"]):
        score += 10

    if any(k in t for k in ["automação", "automacao", "whatsapp", "crm", "funil", "atendimento"]):
        score += 20

    if any(k in t for k in ["humano", "atendente", "equipe", "falar com alguém", "falar com alguem", "pessoa responsável", "pessoa responsavel"]):
        score += 70

    return min(100, max(0, score))


def _derive_temp(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 40:
        return "warm"
    return "cold"


def _detect_theme(text: str) -> str:
    t = (text or "").lower()

    if "landing" in t:
        return "landing_page"
    if any(k in t for k in ["site", "e-commerce", "loja"]):
        return "site"
    if any(k in t for k in ["automação", "automacao", "whatsapp", "crm", "atendimento"]):
        return "automacao_whatsapp"
    if any(k in t for k in ["tráfego", "trafego", "meta ads", "google ads", "anúncio", "anuncio"]):
        return "trafego_pago"
    if any(k in t for k in ["ia", "inteligência artificial", "inteligencia artificial", "agente", "chatbot"]):
        return "inteligencia_artificial"
    if any(k in t for k in ["social media", "instagram"]):
        return "social_media"
    if any(k in t for k in ["marca", "branding", "social media", "instagram"]):
        return "branding"
    if any(k in t for k in ["consultoria", "diagnóstico", "diagnostico"]):
        return "consultoria"
    if any(k in t for k in ["humano", "atendente", "equipe", "pessoa", "falar com alguém", "falar com alguem"]):
        return "humano"

    return "outro"


def _score_from_temperature(value: str, fallback: int) -> int:
    temp = str(value or "").strip().lower()
    if temp in {"hot", "quente"}:
        return max(70, fallback)
    if temp in {"warm", "qualificado", "morno"}:
        return max(40, min(fallback or 50, 69))
    if temp in {"cold", "frio"}:
        return min(fallback, 39)
    return fallback


def _normalize_temperature(value: str, score: int) -> str:
    temp = str(value or "").strip().lower()
    if temp in {"hot", "quente"}:
        return "hot"
    if temp in {"warm", "qualificado", "morno"}:
        return "warm"
    if temp in {"cold", "frio"}:
        return "cold"
    return _derive_temp(score)


def _tags_from_intent(intent: str, score: int, handoff: bool) -> List[str]:
    tags: List[str] = []
    intent = (intent or "").strip().lower()

    tag_map = {
        "site": "site",
        "landing_page": "landing-page",
        "automacao": "automacao",
        "automacao_whatsapp": "automacao",
        "inteligencia_artificial": "ia",
        "trafego_pago": "trafego",
        "branding": "branding",
        "social_media": "social-media",
        "consultoria": "consultoria",
        "humano": "humano",
    }

    if tag_map.get(intent):
        tags.append(tag_map[intent])

    if handoff or score >= 70:
        tags.append("lead-quente")
    elif score >= 40:
        tags.append("lead-qualificado")
    else:
        tags.append("lead-novo")

    return tags


def _default_lead_fields(msg: str, intent: str) -> Dict[str, Any]:
    return {
        "business_name": None,
        "business_type": None,
        "main_goal": msg[:180] if msg else None,
        "service_interest": intent if intent != "outro" else None,
        "urgency": None,
        "budget_signal": None,
        "current_tools": None,
        "current_problem": None,
        "desired_result": None,
        "lead_source": None,
        "team_context": None,
        "funnel_stage": None,
        "last_question_asked": None,
        "last_question_category": None,
        "next_best_question": None,
    }


def _default_briefing(msg: str, intent: str) -> Dict[str, Any]:
    return {
        "summary": msg[:300] if msg else None,
        "pain_points": [],
        "goals": [],
        "recommended_solution": intent if intent != "outro" else None,
        "urgency": None,
        "budget_signal": None,
        "questions_to_julia": [],
        "suggested_next_step": None,
    }


def _format_recent_messages(recent_messages: Optional[List[Dict[str, Any]]]) -> str:
    rows = []
    for item in (recent_messages or [])[-12:]:
        direction = (item.get("direction") or "").strip().lower()
        role = "cliente" if direction == "in" else "mugo"
        text = (item.get("text") or "").strip()
        if text:
            rows.append(f"{role}: {text[:500]}")

    if not rows:
        return "Sem histórico recente disponível."

    return "\n".join(rows)


def _format_lead_context(lead_context: Optional[Dict[str, Any]]) -> str:
    if not lead_context:
        return "Sem contexto comercial salvo."

    safe_context = {
        "memory_summary": lead_context.get("memory_summary"),
        "memory_theme": lead_context.get("memory_theme"),
        "memory_goal": lead_context.get("memory_goal"),
        "memory_notes": lead_context.get("memory_notes"),
        "lead_fields": lead_context.get("lead_fields"),
        "briefing": lead_context.get("briefing"),
        "follow_up": lead_context.get("follow_up"),
        "last_question_asked": lead_context.get("last_question_asked"),
        "last_question_category": lead_context.get("last_question_category"),
        "selected_service": lead_context.get("selected_service"),
        "selected_service_id": lead_context.get("selected_service_id"),
        "intent": lead_context.get("intent"),
        "next_action": lead_context.get("next_action"),
        "meeting_suggested": lead_context.get("meeting_suggested"),
        "briefing_ready": lead_context.get("briefing_ready"),
        "last_user_goal": lead_context.get("last_user_goal"),
        "handoff_done": lead_context.get("handoff_done"),
    }

    try:
        return json.dumps(safe_context, ensure_ascii=False, indent=2)
    except Exception:
        return str(safe_context)


def _extract_json_object(s: str) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    s = s.strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


def _normalize_ai_output(
    out: Dict[str, Any],
    user_message: str,
    flow_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    msg = (user_message or "").strip()
    score_base = _score_from_text(msg)

    out = out or {}

    reply = str(out.get("reply") or "").strip()
    if not reply:
        reply = "Perfeito. Me explica em uma frase o que você quer destravar agora."

    lead_temperature_raw = out.get("lead_temperature") or ""
    score = _score_from_temperature(lead_temperature_raw, score_base)

    handoff = bool(out.get("handoff"))
    intent = str(out.get("intent") or out.get("lead_theme") or "").strip().lower() or _detect_theme(msg)
    if intent == "ia":
        intent = "inteligencia_artificial"
    if intent == "trafego":
        intent = "trafego_pago"
    if intent in {"automacao", "whatsapp", "crm"}:
        intent = "automacao_whatsapp"
    if intent == "indefinido":
        intent = "outro"

    next_action = str(out.get("next_action") or out.get("next_intent") or "").strip().lower()
    if not next_action:
        next_action = "handoff" if handoff else "reply"
    if next_action not in {"reply", "ask_question", "offer_meeting", "handoff", "create_task", "pause_bot", "follow_up"}:
        next_action = "reply"
    if next_action == "handoff":
        handoff = True

    handoff_reason = out.get("handoff_reason")
    handoff_summary = (
        (out.get("handoff_summary") or handoff_reason or out.get("reply") or msg[:220])
    )
    handoff_summary = str(handoff_summary).strip() or msg[:220]

    memory_summary = str(out.get("memory_summary") or handoff_summary or msg[:220]).strip()[:220]
    memory_goal = str(out.get("memory_goal") or msg[:180]).strip()[:180]
    memory_theme = str(out.get("memory_theme") or intent).strip() or intent

    if handoff:
        score = max(score, 70)

    lead_temperature = _normalize_temperature(lead_temperature_raw, score)
    meeting_suggested = bool(out.get("meeting_suggested")) or next_action == "offer_meeting"
    briefing_ready = bool(out.get("briefing_ready")) or handoff

    suggested_tags = out.get("suggested_tags")
    if not isinstance(suggested_tags, list):
        suggested_tags = _tags_from_intent(intent, score, handoff)

    lead_fields = out.get("lead_fields")
    if not isinstance(lead_fields, dict):
        lead_fields = {}

    default_fields = _default_lead_fields(msg, intent)
    default_fields.update({k: v for k, v in lead_fields.items() if k in default_fields})

    briefing = out.get("briefing")
    if not isinstance(briefing, dict):
        briefing = {}
    default_briefing = _default_briefing(msg, intent)
    default_briefing.update({k: v for k, v in briefing.items() if k in default_briefing})
    for list_key in ("pain_points", "goals", "questions_to_julia"):
        if not isinstance(default_briefing.get(list_key), list):
            default_briefing[list_key] = []

    follow_up = out.get("follow_up")
    if not isinstance(follow_up, dict):
        follow_up = {"needed": False, "when": None, "message": None}

    normalized = {
        "reply": reply[:500],
        "intent": intent,
        "next_action": next_action,
        "question_key": (out.get("question_key") or "none"),
        "handoff": handoff,
        "handoff_reason": handoff_reason,
        "handoff_summary": handoff_summary[:500],
        "next_intent": next_action,
        "lead_score": max(0, min(100, score)),
        "lead_temperature": lead_temperature,
        "lead_theme": intent,
        "meeting_suggested": meeting_suggested,
        "briefing_ready": briefing_ready,
        "suggested_tags": [str(tag).strip() for tag in suggested_tags if str(tag).strip()][:8],
        "lead_fields": default_fields,
        "briefing": {
            "summary": default_briefing.get("summary"),
            "pain_points": [str(x).strip() for x in default_briefing.get("pain_points", []) if str(x).strip()][:8],
            "goals": [str(x).strip() for x in default_briefing.get("goals", []) if str(x).strip()][:8],
            "recommended_solution": default_briefing.get("recommended_solution"),
            "urgency": default_briefing.get("urgency"),
            "budget_signal": default_briefing.get("budget_signal"),
            "questions_to_julia": [str(x).strip() for x in default_briefing.get("questions_to_julia", []) if str(x).strip()][:8],
            "suggested_next_step": default_briefing.get("suggested_next_step"),
        },
        "follow_up": {
            "needed": bool(follow_up.get("needed")),
            "when": follow_up.get("when"),
            "message": follow_up.get("message"),
        },
        "memory_summary": memory_summary,
        "memory_theme": memory_theme,
        "memory_goal": memory_goal,
    }

    if handoff and normalized["lead_temperature"] == "cold":
        normalized["lead_temperature"] = "hot"

    if flow_context:
        normalized["handoff"] = True
        normalized["next_intent"] = "flow_handoff"
        normalized["next_action"] = "handoff"
        normalized["lead_score"] = max(70, normalized["lead_score"])
        normalized["lead_temperature"] = "hot"
        normalized["briefing_ready"] = True
        if normalized["lead_theme"] == "outro":
            normalized["lead_theme"] = "consultoria"
            normalized["intent"] = "consultoria"
        normalized["memory_theme"] = normalized["lead_theme"]

    return normalized


async def generate_reply(
    user_message: str,
    wa_id: str = "",
    first_message_sent: bool = True,
    name: str = "",
    telefone: str = "",
    flow_context: Optional[Dict[str, Any]] = None,
    recent_messages: Optional[List[Dict[str, Any]]] = None,
    lead_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    msg = (user_message or "").strip()
    if not msg:
        return _fallback(user_message)

    if not OPENAI_API_KEY:
        _ai_log("fallback_no_api_key", wa_id=wa_id, text_len=len(msg), flow_context=bool(flow_context))
        out = _fallback(user_message)

        if flow_context:
            out["reply"] = "Perfeito. Já entendi o cenário e vou te encaminhar agora para um especialista dar sequência."
            out["handoff"] = True
            out["next_action"] = "handoff"
            out["next_intent"] = "flow_handoff"
            out["handoff_reason"] = "briefing_concluido"
            out["handoff_summary"] = msg[:220]
            out["lead_score"] = max(70, out["lead_score"])
            out["lead_temperature"] = "hot"
            out["briefing_ready"] = True
            out["lead_theme"] = "consultoria"
            out["intent"] = "consultoria"
            out["memory_summary"] = msg[:220]
            out["memory_theme"] = "consultoria"
            out["memory_goal"] = msg[:180]
            return out

        if out["lead_score"] >= 50:
            out["handoff"] = True
            out["next_action"] = "handoff"
            out["next_intent"] = "ai_handoff"
            out["handoff_reason"] = "lead_com_intencao_comercial"
            out["lead_score"] = max(85, out["lead_score"])
            out["lead_temperature"] = "hot"
            out["meeting_suggested"] = True

        return out

    flow_txt = ""
    if flow_context:
        try:
            flow_txt = json.dumps(flow_context, ensure_ascii=False)
        except Exception:
            flow_txt = str(flow_context)

    lead_profile = {
        "wa_id": wa_id,
        "name": name,
        "telefone": telefone,
        "first_message_sent": first_message_sent,
        "flow_context": flow_context or {},
    }

    official_prompt = load_mugo_prompt()
    history_text = _format_recent_messages(recent_messages)
    lead_context_text = _format_lead_context(lead_context)

    if flow_context:
        flow_txt = (
            f"{flow_txt}\n\nO lead concluiu um mini-briefing estruturado. "
            "Confirme em até 2 linhas, não faça novas perguntas e marque handoff=true."
        )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": official_prompt},
            {"role": "system", "content": f"Histórico recente da conversa:\n{history_text}"},
            {"role": "system", "content": f"Contexto comercial salvo do lead:\n{lead_context_text}"},
            {"role": "system", "content": f"Perfil técnico do lead:\n{json.dumps(lead_profile, ensure_ascii=False)}"},
            {"role": "system", "content": f"Contexto do fluxo atual:\n{flow_txt or 'Nenhum.'}"},
            {"role": "user", "content": msg},
        ],
        "temperature": 0.3,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }

    try:
        _ai_log(
            "request",
            wa_id=wa_id,
            model=OPENAI_MODEL,
            text_len=len(msg),
            recent_messages=len(recent_messages or []),
            has_lead_context=bool(lead_context),
            has_flow_context=bool(flow_context),
        )
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if r.status_code >= 300:
            _ai_log("http_error", wa_id=wa_id, status_code=r.status_code, body=(r.text or "")[:500])
            return _fallback(user_message)

        content = (r.json().get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
        content = content.strip()

        out = _extract_json_object(content)
        if not out or not isinstance(out, dict):
            _ai_log("json_error", wa_id=wa_id, content_preview=content[:500])
            return _fallback(user_message)

        normalized = _normalize_ai_output(out, user_message, flow_context=flow_context)
        _ai_log(
            "response",
            wa_id=wa_id,
            intent=normalized.get("intent"),
            next_action=normalized.get("next_action"),
            lead_temperature=normalized.get("lead_temperature"),
            handoff=normalized.get("handoff"),
            meeting_suggested=normalized.get("meeting_suggested"),
            briefing_ready=normalized.get("briefing_ready"),
        )
        return normalized

    except Exception as e:
        _ai_log("exception", wa_id=wa_id, error=repr(e))
        return _fallback(user_message)
