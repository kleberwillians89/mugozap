import os
import json
from typing import Any, Dict, Optional
import httpx

OPENAI_API_KEY = (
    os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_KEY")
    or ""
).strip()

OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT") or "12")


def _fallback(user_message: str) -> Dict[str, Any]:
    msg = (user_message or "").strip()
    return {
        "reply": "Perfeito. Me explica em uma frase o que você quer destravar agora.",
        "intent": "geral",
        "question_key": "none",
        "handoff": False,
        "handoff_summary": msg[:220],
        "next_intent": "next",
        "lead_score": 10,
        "lead_temperature": "frio",
        "lead_theme": "indefinido",
    }


def _score_from_text(t: str) -> int:
    t = (t or "").lower()
    score = 0

    if any(k in t for k in ["orçamento", "orcamento", "preço", "preco", "valor", "proposta", "quanto custa"]):
        score += 35

    if any(k in t for k in ["prazo", "urgente", "hoje", "amanhã", "essa semana"]):
        score += 20

    if any(k in t for k in ["fechar", "contrato", "assinar", "começar", "comecar"]):
        score += 25

    return min(100, max(0, score))


def generate_reply(
    wa_id: str,
    user_message: str,
    first_message_sent: bool,
    name: str = "",
    telefone: str = "",
    flow_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    msg = (user_message or "").strip()
    if not msg:
        return _fallback(user_message)

    # se não tiver chave, não quebra deploy
    if not OPENAI_API_KEY:
        out = _fallback(user_message)
        s = _score_from_text(msg)
        if s >= 60:
            out["handoff"] = True
            out["next_intent"] = "ai_handoff"
            out["lead_score"] = 85
            out["lead_temperature"] = "quente"
        return out

    flow_txt = ""
    if flow_context:
        try:
            flow_txt = json.dumps(flow_context, ensure_ascii=False)
        except Exception:
            flow_txt = str(flow_context)

    system_prompt = (
        "Você é um SDR estratégico da Mugô.\n"
        "Responda de forma clara, direta e estratégica.\n"
        "Máximo 3 linhas.\n"
        "Se faltar informação, faça 1 pergunta objetiva.\n"
        "Nunca responda fora do JSON.\n"
        "Retorne JSON com as chaves:\n"
        "reply, intent, question_key, handoff, handoff_summary, next_intent, lead_score, lead_temperature, lead_theme"
    )

    user_prompt = (
        f"WA_ID: {wa_id}\n"
        f"Nome: {name}\n"
        f"Telefone: {telefone}\n"
        f"Mensagem: {msg}\n"
        f"Contexto do fluxo: {flow_txt}\n"
        "Responda em JSON."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 250,
    }

    try:
        with httpx.Client(timeout=OPENAI_TIMEOUT) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if r.status_code >= 300:
            return _fallback(user_message)

        content = r.json()["choices"][0]["message"]["content"].strip()

        try:
            out = json.loads(content)
        except Exception:
            return _fallback(user_message)

        if not isinstance(out, dict) or not out.get("reply"):
            return _fallback(user_message)

        out.setdefault("intent", "geral")
        out.setdefault("question_key", "none")
        out.setdefault("handoff", False)
        out.setdefault("handoff_summary", msg[:220])
        out.setdefault("next_intent", "next")
        out.setdefault("lead_score", _score_from_text(msg))
        out.setdefault("lead_theme", "indefinido")

        try:
            score = int(out.get("lead_score") or 0)
        except Exception:
            score = _score_from_text(msg)

        if score >= 70:
            temp = "quente"
        elif score >= 40:
            temp = "qualificado"
        else:
            temp = "frio"

        out["lead_temperature"] = temp

        return out

    except Exception:
        return _fallback(user_message)