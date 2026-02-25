# mugo-zap/server/services/openai_client.py
import os
import json
import re
from typing import Any, Dict, Optional

import httpx

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()

# respostas rápidas: não deixa travar campanha
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT") or "10")

_TIMEOUT = httpx.Timeout(connect=5.0, read=OPENAI_TIMEOUT, write=10.0, pool=10.0)
_CLIENT = httpx.Client(timeout=_TIMEOUT)

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _fallback(user_message: str) -> Dict[str, Any]:
    msg = (user_message or "").strip()
    return {
        "reply": "Perfeito. Me diz em uma frase o que você quer destravar agora (pra eu te encaminhar certo).",
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


def _strip_json_fences(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    s = _JSON_FENCE_RE.sub("", s).strip()
    return s


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

    # Sem chave: mantém vivo e ainda dá “inteligência mínima”
    if not OPENAI_API_KEY:
        out = _fallback(user_message)
        s = _score_from_text(msg)
        out["lead_score"] = max(out.get("lead_score", 10), s)
        if s >= 60:
            out["handoff"] = True
            out["next_intent"] = "ai_handoff"
            out["lead_score"] = 85
            out["lead_temperature"] = "quente"
        return out

    flow_txt = ""
    if isinstance(flow_context, dict) and flow_context:
        try:
            # contexto compacto (evita token/latência)
            compact = {
                "macro": flow_context.get("macro"),
                "service_interest": flow_context.get("service_interest"),
                "briefing_text": flow_context.get("briefing_text"),
                "cta_choice": flow_context.get("cta_choice"),
                "lead_name": flow_context.get("lead_name"),
            }
            flow_txt = json.dumps(compact, ensure_ascii=False)
        except Exception:
            flow_txt = str(flow_context)

    system = (
        "Você é um SDR/Closer da Mugô.\n"
        "Objetivo: responder com clareza e encaminhar para humano quando fizer sentido.\n"
        "Regras:\n"
        "- Respostas curtas (máx 2-4 linhas).\n"
        "- Sem promessas absolutas.\n"
        "- Se faltar info, faça 1 pergunta objetiva.\n"
        "Saída: JSON puro (sem texto fora do JSON) com chaves:\n"
        "reply, intent, question_key, handoff, handoff_summary, next_intent, lead_score, lead_temperature, lead_theme\n"
    )

    user = (
        f"WA_ID: {wa_id}\n"
        f"Nome: {name}\n"
        f"Telefone: {telefone}\n"
        f"Mensagem: {msg}\n"
        f"Contexto do funil: {flow_txt}\n"
        "Responda no formato JSON."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 220,
    }

    try:
        r = _CLIENT.post(
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
        content = _strip_json_fences(content)

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
        out.setdefault("lead_temperature", "frio")
        out.setdefault("lead_theme", "indefinido")

        try:
            s = int(out.get("lead_score") or 0)
        except Exception:
            s = _score_from_text(msg)

        if s >= 70:
            out["lead_temperature"] = "quente"
        elif s >= 40:
            out["lead_temperature"] = "qualificado"
        else:
            out["lead_temperature"] = "frio"

        return out

    except Exception:
        return _fallback(user_message)