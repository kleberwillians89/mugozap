import os
import json
import re
import uuid
import urllib.parse
import traceback
import asyncio
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse


def _load_env() -> Path:
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)
            return p
    return candidates[0]


ENV_PATH = _load_env()

VERIFY_TOKEN = (os.getenv("WHATSAPP_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN") or "mugo_verify").strip()
ALLOW_ORIGIN = (os.getenv("ALLOW_ORIGIN") or "").strip()
PANEL_API_KEY = (os.getenv("PANEL_API_KEY") or "").strip()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_API_KEY = SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY

SUPABASE_TABLE_CONVERSATIONS = (
    os.getenv("SUPABASE_TABLE_CONVERSATIONS")
    or os.getenv("WA_CONVERSATIONS_TABLE")
    or "whatsapp_conversations"
).strip()
SUPABASE_TABLE_USERS = (
    os.getenv("SUPABASE_TABLE_USERS")
    or os.getenv("WA_USERS_TABLE")
    or "whatsapp_users"
).strip()
SUPABASE_TABLE_MESSAGES = (
    os.getenv("SUPABASE_TABLE_MESSAGES")
    or os.getenv("WA_MESSAGES_TABLE")
    or "whatsapp_messages"
).strip()
SUPABASE_TABLE_TASKS = (
    os.getenv("SUPABASE_TABLE_TASKS")
    or os.getenv("WA_TASKS_TABLE")
    or "whatsapp_tasks"
).strip()
SUPABASE_TABLE_AI_STATE = (os.getenv("SUPABASE_TABLE_AI_STATE") or "ai_state").strip()
SUPABASE_TABLE_FLOW_STATE = (
    os.getenv("SUPABASE_TABLE_FLOW_STATE")
    or os.getenv("WA_FLOW_STATE_TABLE")
    or "whatsapp_flow_state"
).strip()

HUMAN_NUMBER = (os.getenv("HUMAN_NUMBER") or "5511973510549").strip()
DEBUG_WEBHOOK = (os.getenv("DEBUG_WEBHOOK") or "").strip().lower() in ("1", "true", "yes")

WA_USERS_TABLE = SUPABASE_TABLE_USERS
WA_MESSAGES_TABLE = SUPABASE_TABLE_MESSAGES
WA_TASKS_TABLE = SUPABASE_TABLE_TASKS

INTERNAL_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in (os.getenv("INTERNAL_ALLOWED_DOMAINS") or "mugo.ag").split(",")
    if d.strip()
]

INTERNAL_ALLOWED_EMAILS = {
    e.strip().lower()
    for e in (os.getenv("INTERNAL_ALLOWED_EMAILS") or "").split(",")
    if e.strip()
}

DEFAULT_INTERNAL_ROLE = (os.getenv("DEFAULT_INTERNAL_ROLE") or "staff").strip()
DEFAULT_ASSIGNEE = (os.getenv("DEFAULT_ASSIGNEE") or "Julia").strip()
EDUARDA_NUMBER = (os.getenv("EDUARDA_NUMBER") or "558192955061").strip()

from services.ai_state import get_ai_state, upsert_ai_state, reset_ai_state
from services.state import (
    mark_first_message_sent,
    log_message,
    list_conversations,
    get_recent_messages,
    get_flow,
    merge_flow_data,
    set_handoff_pending,
    set_handoff_topic,
    clear_handoff,
    upsert_user,
    create_task,
    list_tasks,
    done_task,
    update_task,
    clear_flow,
    set_tags,
    normalize_wa_id,
)
from services.whatsapp import meta_env_status, send_message, send_message_detailed
from services.openai_client import generate_reply
from services.mugo_flow import apply_service_choice, handle_mugo_flow, is_service_choice, service_choice_context
from services import sales_brain
from services.followup import process_followups
from services.workspace import build_default_workspace, ensure_default_workspace, resolve_workspace_id

app = FastAPI(title="MugôZap API")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("\n=== UNHANDLED SERVER ERROR ===")
    print("PATH:", request.url.path)
    print("ERROR:", repr(exc))
    traceback.print_exc()
    print("=== /UNHANDLED SERVER ERROR ===\n")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.on_event("startup")
async def startup_check():
    print("BOOT ENV CHECK:")
    print("ENV_PATH:", str(ENV_PATH))
    print("SUPABASE_URL:", (SUPABASE_URL[:45] + "...") if SUPABASE_URL else "MISSING")
    print("SUPABASE_API_KEY:", (SUPABASE_API_KEY[:10] + "...") if SUPABASE_API_KEY else "MISSING")
    print("PANEL_API_KEY:", PANEL_API_KEY if PANEL_API_KEY else "MISSING")
    print("INTERNAL_ALLOWED_DOMAINS:", INTERNAL_ALLOWED_DOMAINS)
    print("DEFAULT_ASSIGNEE:", DEFAULT_ASSIGNEE)
    print("HUMAN_NUMBER:", HUMAN_NUMBER)
    print("EDUARDA_NUMBER:", EDUARDA_NUMBER)
    print("SUPABASE_TABLE_CONVERSATIONS:", SUPABASE_TABLE_CONVERSATIONS)
    print("SUPABASE_TABLE_USERS:", SUPABASE_TABLE_USERS)
    print("SUPABASE_TABLE_MESSAGES:", SUPABASE_TABLE_MESSAGES)
    print("SUPABASE_TABLE_TASKS:", SUPABASE_TABLE_TASKS)
    print("SUPABASE_TABLE_AI_STATE:", SUPABASE_TABLE_AI_STATE)
    print("SUPABASE_TABLE_FLOW_STATE:", SUPABASE_TABLE_FLOW_STATE)
    meta_env = meta_env_status()
    print("WHATSAPP_TOKEN:", "present" if meta_env["whatsapp_token_present"] else "missing")
    print("WHATSAPP_PHONE_NUMBER_ID:", meta_env["whatsapp_phone_number_id"] or "missing")
    print("WHATSAPP_VERIFY_TOKEN:", "present" if meta_env["whatsapp_verify_token_present"] else "missing")
    print("META_APP_SECRET:", "present" if meta_env["meta_app_secret_present"] else "missing")
    print("DEFAULT_WORKSPACE:", build_default_workspace())

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    if not SUPABASE_API_KEY:
        raise RuntimeError("Missing SUPABASE_ANON_KEY (or SERVICE_ROLE fallback) in .env")

    workspace = await ensure_default_workspace()
    print("DEFAULT_WORKSPACE_READY:", workspace)


ALLOW_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://mugo-zap-web.onrender.com",
]
if ALLOW_ORIGIN:
    ALLOW_ORIGINS.append(ALLOW_ORIGIN)

_seen = set()
ALLOW_ORIGINS = [o for o in ALLOW_ORIGINS if not (o in _seen or _seen.add(o))]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _supabase_get_user(access_token: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        raise HTTPException(status_code=500, detail="Supabase env not configured")

    access_token = (access_token or "").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "apikey": SUPABASE_API_KEY,
                },
            )
    except httpx.HTTPError as e:
        print("SUPABASE AUTH ERROR:", repr(e))
        raise HTTPException(status_code=503, detail="Auth service temporarily unavailable")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return resp.json()


def _is_allowed_internal_user(user: dict) -> bool:
    email = ((user or {}).get("email") or "").strip().lower()
    if not email:
        return False

    if email in INTERNAL_ALLOWED_EMAILS:
        return True

    if "@" in email:
        domain = email.split("@", 1)[1].strip().lower()
        if domain in INTERNAL_ALLOWED_DOMAINS:
            return True

    return False


def _build_internal_user_payload(user: dict) -> dict:
    email = ((user or {}).get("email") or "").strip().lower()
    metadata = (user or {}).get("user_metadata") or {}
    app_metadata = (user or {}).get("app_metadata") or {}

    role = metadata.get("role") or app_metadata.get("role") or DEFAULT_INTERNAL_ROLE
    workspace_id = resolve_workspace_id(user=user)
    workspace = build_default_workspace()
    workspace["id"] = workspace_id

    return {
        "id": user.get("id"),
        "email": email,
        "name": metadata.get("name") or metadata.get("full_name") or email,
        "role": role,
        "workspace_id": workspace_id,
        "workspace": workspace,
    }


async def get_current_user(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
) -> dict:
    panel_key = (x_panel_key or "").strip()
    requested_workspace_id = resolve_workspace_id(explicit_workspace_id=x_workspace_id)

    if PANEL_API_KEY and panel_key and panel_key == PANEL_API_KEY:
        return {
            "id": "panel-key",
            "email": "panel@mugo.internal",
            "name": "Painel Mugô",
            "role": "admin",
            "auth_mode": "panel_key",
            "workspace_id": requested_workspace_id,
            "workspace": {
                **build_default_workspace(),
                "id": requested_workspace_id,
            },
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    user = await _supabase_get_user(token)
    internal_user = _build_internal_user_payload(user)

    if not _is_allowed_internal_user(user):
        raise HTTPException(status_code=403, detail="User not allowed in internal panel")

    internal_user["auth_mode"] = "supabase"
    internal_user["workspace_id"] = resolve_workspace_id(
        explicit_workspace_id=requested_workspace_id,
        user=internal_user,
    )
    internal_user["workspace"] = {
        **build_default_workspace(),
        "id": internal_user["workspace_id"],
    }
    return internal_user


def _j(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _menu_fallback_text() -> str:
    return (
        "Oi! Sou a IA da Mugô. Para te ajudar melhor, me diz o que você procura?\n"
        "1. Criar site ou landing page\n"
        "2. Automatizar WhatsApp/atendimento\n"
        "3. Usar IA no meu negócio\n"
        "4. Tráfego pago/performance\n"
        "5. Branding/conteúdo/redes sociais\n"
        "6. Falar com a equipe"
    )


def _outbound_preview(payload: Union[str, Dict[str, Any]]) -> str:
    return _extract_log_text(payload)[:220] if isinstance(payload, dict) else str(payload or "")[:220]


def _log_outbound_decision(cid: str, wa_id: str, kind: str, reply: Union[str, Dict[str, Any]]) -> None:
    print(
        "OUTBOUND_DECISION "
        f"cid={cid} wa_id={wa_id} kind={kind} reply_preview={_outbound_preview(reply)!r}"
    )


def _log_outbound_skipped(cid: str, wa_id: str, reason: str) -> None:
    print(f"OUTBOUND_SKIPPED cid={cid} wa_id={wa_id} reason={reason}")


def _extract_inbound_wa_id(msg: dict, contacts: list | None = None) -> tuple[str, str]:
    contacts = contacts or []
    contact_wa_id = ((contacts[0] or {}).get("wa_id") or "").strip() if contacts else ""
    message_from = (msg.get("from") or "").strip()

    candidates = [message_from, contact_wa_id]
    normalized_candidates = [normalize_wa_id(value) for value in candidates if normalize_wa_id(value)]
    normalized_candidates.sort(key=lambda value: (len(value), value), reverse=True)

    raw = next((value for value in candidates if value), "")
    normalized = normalized_candidates[0] if normalized_candidates else ""
    return raw, normalized


def _is_back_trigger(lower: str) -> bool:
    lower = (lower or "").strip().lower()
    return lower in {"voltar", "volta", "menu", "início", "inicio", "robô", "robo", "bot"}


def _is_post_handoff_mode(ai_state: dict) -> bool:
    return bool((ai_state or {}).get("handoff_done"))


def _flow_data(wa_id: str, workspace_id: str = "") -> Dict[str, Any]:
    flow = get_flow(wa_id, workspace_id=workspace_id) or {}
    data = flow.get("data") or {}
    return data if isinstance(data, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, limit: int = 900) -> str:
    return str(value or "").strip()[:limit]


def _apply_operational_state(
    wa_id: str,
    *,
    workspace_id: str = "",
    status: str = "",
    step: str = "",
    waiting_for: str = "",
    user_patch: dict | None = None,
    flow_patch: dict | None = None,
    event: str = "",
) -> None:
    user_payload = dict(user_patch or {})
    flow_payload = dict(flow_patch or {})

    if status:
        flow_payload["bot_status"] = status
    if step:
        flow_payload["current_step"] = step
        flow_payload["flow_step"] = step
    if waiting_for:
        flow_payload["waiting_for"] = waiting_for

    if event:
        print(f"FLOW:{event} wa_id={wa_id} status={status or flow_payload.get('bot_status') or ''} step={step or flow_payload.get('current_step') or ''}")

    try:
        if user_payload:
            upsert_user(wa_id, workspace_id=workspace_id, **user_payload)
    except Exception:
        pass

    try:
        if flow_payload:
            merge_flow_data(wa_id, flow_payload, workspace_id=workspace_id)
    except Exception:
        pass


def _build_conversation_context(flow_data: Dict[str, Any], ai_state: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}

    for key in (
        "topic",
        "problem",
        "briefing",
        "free_text_need",
        "current_step",
        "bot_status",
        "flow_step",
        "resume_mode",
        "context_summary",
        "last_handoff_closed_at",
        "last_bot_text",
        "last_bot_at",
        "last_ai_text",
        "last_ai_at",
        "last_human_text",
        "last_human_at",
        "last_user_text",
        "last_user_at",
        "waiting_for",
        "handoff_reason",
        "handoff_started_at",
        "handoff_closed_at",
        "resumed_at",
        "followup_due_at",
        "repeat_guard_hits",
    ):
        value = (flow_data or {}).get(key)
        if isinstance(value, str) and value.strip():
            context[key] = value.strip()

    for key in ("memory_summary", "memory_theme", "memory_goal", "handoff_summary"):
        value = (ai_state or {}).get(key)
        if isinstance(value, str) and value.strip():
            context[key] = value.strip()

    return context


def _build_recent_history_text(wa_id: str, workspace_id: str = "", limit: int = 8) -> str:
    try:
        history = get_recent_messages(wa_id, limit=limit, workspace_id=workspace_id) or []
    except Exception:
        history = []

    lines: List[str] = []
    for item in history[-limit:]:
        direction = "Lead" if (item.get("direction") or "").strip() == "in" else "Mugô"
        text = (item.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{direction}: {text[:220]}")

    return "\n".join(lines[-limit:])[:1800]


def _build_resume_message(flow_data: Dict[str, Any], ai_state: Dict[str, Any]) -> str:
    context_summary = ((flow_data or {}).get("context_summary") or "").strip()
    handoff_summary = ((ai_state or {}).get("handoff_summary") or "").strip()
    topic = ((flow_data or {}).get("topic") or (ai_state or {}).get("handoff_topic") or "").strip()

    base = "Você conseguiu tirar todas as suas dúvidas com Julia? Posso continuar daqui com você."

    if context_summary:
        return f"{base}\n\nPelo que ficou registrado: {context_summary[:240]}"
    if handoff_summary:
        return f"{base}\n\nSe quiser, eu continuo a partir deste contexto: {handoff_summary[:240]}"
    if topic:
        return f"{base}\n\nSe fizer sentido, seguimos a partir de {topic}."
    return base


def _is_resume_ready(flow_data: Dict[str, Any], user: Dict[str, Any] | None = None) -> bool:
    if not isinstance(flow_data, dict):
        return False
    if bool((user or {}).get("handoff_active")):
        return False
    return (flow_data.get("resume_mode") or "").strip() == "awaiting_customer_after_handoff"


def _should_skip_duplicate_bot_message(wa_id: str, step_key: str, bot_text: str, workspace_id: str = "") -> bool:
    flow_data = _flow_data(wa_id, workspace_id=workspace_id)
    last_step = (flow_data.get("last_bot_step") or "").strip()
    last_text = (flow_data.get("last_bot_text") or "").strip()
    should_block = bool(step_key and bot_text and last_step == step_key and last_text == bot_text)
    if should_block:
        hits = int(flow_data.get("repeat_guard_hits") or 0) + 1
        merge_flow_data(
            wa_id,
            {
                "repeat_guard_hits": hits,
                "last_repeat_block_reason": f"{step_key}:{bot_text[:80]}",
            },
            workspace_id=workspace_id,
        )
        print(f"FLOW:repeat_block wa_id={wa_id} step={step_key} hits={hits}")
    return should_block


def _remember_bot_message(wa_id: str, step_key: str, bot_text: str, workspace_id: str = "") -> None:
    if not wa_id or not bot_text:
        return

    flow_data = _flow_data(wa_id, workspace_id=workspace_id)
    patch: Dict[str, Any] = {
        "last_bot_text": bot_text[:900],
        "last_bot_at": _now_iso(),
        "last_ai_text": bot_text[:900] if step_key == "ai_reply" or step_key == "resume_after_handoff" else (flow_data.get("last_ai_text") or ""),
        "last_ai_at": _now_iso() if step_key == "ai_reply" or step_key == "resume_after_handoff" else (flow_data.get("last_ai_at") or ""),
        "bot_paused": False,
    }

    if step_key:
        patch["last_bot_step"] = step_key
        patch["current_step"] = step_key

    if step_key == "step_01" and not flow_data.get("welcome_sent_at"):
        patch["welcome_sent_at"] = datetime.now(timezone.utc).isoformat()

    merge_flow_data(wa_id, patch, workspace_id=workspace_id)


def _extract_auto_tags(result: dict) -> List[str]:
    tags: List[str] = []
    suggested = (result or {}).get("suggested_tags") or []
    if isinstance(suggested, list):
        tags.extend([str(tag).strip() for tag in suggested if str(tag).strip()])

    theme = ((result or {}).get("lead_theme") or "").strip().lower()
    score = int((result or {}).get("lead_score") or 0)
    handoff = bool((result or {}).get("handoff"))

    if "crm" in theme:
        tags.append("crm")
    if "site" in theme or "landing" in theme or "e-commerce" in theme:
        tags.append("site")
    if "autom" in theme or "whatsapp" in theme:
        tags.append("automacao")
    if "ia" in theme or "intelig" in theme or "chatbot" in theme:
        tags.append("ia")
    if "social" in theme or "branding" in theme or "instagram" in theme:
        tags.append("social-media")
    if "traf" in theme or "ads" in theme:
        tags.append("trafego")

    if handoff or score >= 70:
        tags.append("lead-quente")
    elif score >= 40:
        tags.append("lead-qualificado")
    else:
        tags.append("lead-novo")

    deduped = []
    seen = set()
    for tag in tags:
        if tag and tag not in seen:
            deduped.append(tag)
            seen.add(tag)
    return deduped


def _merge_lead_fields(old_fields: dict | None, new_fields: dict | None) -> dict:
    merged = dict(old_fields or {})
    for key, value in (new_fields or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def _merge_briefing(old_briefing: dict | None, new_briefing: dict | None) -> dict:
    merged = dict(old_briefing or {})
    for key, value in (new_briefing or {}).items():
        if isinstance(value, list):
            old_items = merged.get(key) if isinstance(merged.get(key), list) else []
            seen = {str(x).strip() for x in old_items if str(x).strip()}
            additions = [str(x).strip() for x in value if str(x).strip() and str(x).strip() not in seen]
            merged[key] = (old_items + additions)[:8]
        elif value not in (None, "", {}):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def _compact_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w\s/]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _question_key(text: str) -> str:
    compact = _compact_text(text)
    if "vendas/leads" in compact or ("vendas" in compact and "operação" in compact):
        return "main_goal"
    if "vender mais" in compact and "ganhar tempo" in compact:
        return "main_goal"
    if "foco hoje" in compact and ("vender" in compact or "organizar" in compact):
        return "main_goal"
    if "whatsapp" in compact and "instagram" in compact and "site" in compact:
        return "lead_source"
    if "crm" in compact or "manual" in compact or "ferramenta" in compact:
        return "current_tools"
    if "este mês" in compact or "essa semana" in compact or "fase de entender" in compact or "curto prazo" in compact:
        return "urgency"
    if "verba" in compact or "orçamento" in compact or "investimento" in compact:
        return "budget_signal"
    if "julia" in compact and ("encaminhar" in compact or "resumo" in compact):
        return "offer_meeting"
    return compact[:90]


def _extract_last_question(text: str) -> str:
    text = str(text or "").strip()
    if "?" not in text:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[?])", text) if "?" in part]
    return parts[-1][-240:] if parts else text[-240:]


def _infer_fields_from_text(user_text: str, ai_state: dict | None, result: dict | None = None) -> dict:
    text = _compact_text(user_text)
    state_fields = ((ai_state or {}).get("lead_fields") or {})
    result_fields = ((result or {}).get("lead_fields") or {})
    brain_state = sales_brain.merge_state(sales_brain.flatten_state(ai_state or {}), result_fields)
    brain_updates = sales_brain.extract_signal_from_message(user_text, brain_state)
    service_interest = result_fields.get("service_interest") or state_fields.get("service_interest") or (ai_state or {}).get("selected_service")
    last_question_category = (
        result_fields.get("last_question_category")
        or state_fields.get("last_question_category")
        or (ai_state or {}).get("last_question_category")
        or _question_key(state_fields.get("last_question_asked") or (ai_state or {}).get("last_question_asked") or "")
    )
    inferred: dict = dict(brain_updates)

    if service_interest:
        inferred["service_interest"] = service_interest

    if any(k in text for k in ["vendas", "vender", "vender mais", "mais vendas", "aumentar venda", "aumentar as vendas", "gerar lead", "gerar leads", "mais clientes", "cliente", "clientes", "vender pelo whatsapp", "perco vendas", "perder vendas"]):
        inferred["main_goal"] = "vendas/leads"
        inferred["desired_result"] = "vender mais / gerar mais vendas"
        inferred["funnel_stage"] = "qualificacao"
        if service_interest == "automacao_whatsapp":
            inferred["service_interest"] = "automacao_whatsapp"

    if any(k in text for k in ["tempo", "ganhar tempo", "responder mais rápido", "responder mais rapido", "diminuir trabalho", "automatizar", "automatizar atendimento", "não perder mensagem", "nao perder mensagem"]):
        inferred["main_goal"] = inferred.get("main_goal") or "operação/tempo"
        inferred["current_problem"] = inferred.get("current_problem") or "atendimento manual ou mensagens perdidas"
        inferred["funnel_stage"] = "qualificacao"

    if any(k in text for k in ["organizar contatos", "crm", "funil", "acompanhar clientes"]):
        inferred["main_goal"] = inferred.get("main_goal") or "gestão/comercial"
        inferred["current_tools"] = "CRM/funil" if "crm" in text or "funil" in text else inferred.get("current_tools")
        inferred["funnel_stage"] = "qualificacao"

    if any(k in text for k in ["quero site", "landing", "página", "pagina"]):
        inferred["service_interest"] = "landing_page" if "landing" in text else "site"

    if any(k in text for k in ["whatsapp", "atendimento automático", "atendimento automatico", "bot", "automação", "automacao"]):
        inferred["service_interest"] = inferred.get("service_interest") or "automacao_whatsapp"

    if any(k in text for k in ["ia", "inteligência artificial", "inteligencia artificial", "agente"]):
        inferred["service_interest"] = inferred.get("service_interest") or "inteligencia_artificial"

    sources = []
    if "instagram" in text or "direct" in text:
        sources.append("Instagram")
    if "whatsapp" in text:
        sources.append("WhatsApp")
    if "site" in text and (last_question_category == "lead_source" or sources):
        sources.append("site")
    if "indicação" in text or "indicacao" in text:
        sources.append("indicação")
    if sources:
        inferred["lead_source"] = " e ".join(dict.fromkeys(sources))

    if any(k in text for k in ["tudo manual", "manual", "fazemos na mão", "fazemos na mao", "na mão", "na mao", "sem crm", "planilha", "sem ferramenta"]):
        inferred["current_tools"] = "manual"
        inferred["current_problem"] = inferred.get("current_problem") or "atendimento e acompanhamento manual"
        inferred["funnel_stage"] = "qualificacao"

    if any(k in text for k in ["loja", "ecommerce", "e commerce", "restaurante", "clínica", "clinica", "empresa"]):
        inferred["business_type"] = "loja" if "loja" in text else inferred.get("business_type")

    if any(k in text for k in ["essa semana", "esta semana", "urgente", "pra já", "pra ja", "para já", "para ja", "hoje", "amanhã", "amanha", "este mês", "esse mes", "campanha", "curto prazo"]):
        inferred["urgency"] = "alta" if any(k in text for k in ["urgente", "pra já", "pra ja", "para já", "para ja", "hoje", "essa semana", "esta semana"]) else "curto prazo"
        inferred["funnel_stage"] = "decisao"

    if any(k in text for k in ["verba", "orçamento", "orcamento", "budget", "investir", "proposta"]):
        inferred["budget_signal"] = "tem sinal de orçamento/verba"

    if any(k in text for k in ["falar com alguém", "falar com alguem", "atendente", "humano", "pessoa", "equipe", "consultor"]):
        inferred["funnel_stage"] = "handoff"

    return inferred


def _progress_stage_for_fields(fields: dict) -> str:
    next_q = sales_brain.get_next_question(fields)
    category = next_q.get("category") or ""
    if category == "service_interest":
        return "identificar_interesse"
    if category in {"main_goal", "site_scope"}:
        return "identificar_objetivo"
    if category in {"lead_source", "current_tools", "current_status", "current_problem"}:
        return "entender_cenario_atual"
    if category in {"urgency", "budget_signal"}:
        return "entender_urgencia"
    if category in {"offer_meeting", "handoff"}:
        return "encaminhar"
    if not fields.get("service_interest"):
        return "identificar_interesse"
    if not fields.get("main_goal"):
        return "identificar_objetivo"
    if not fields.get("lead_source"):
        return "entender_cenario_origem"
    if not fields.get("current_tools") and not fields.get("current_problem"):
        return "entender_cenario_processo"
    if not fields.get("urgency"):
        return "entender_urgencia"
    return "encaminhar"


def _next_question_for_fields(fields: dict) -> tuple[str, str]:
    next_q = sales_brain.get_next_question(fields)
    return next_q.get("category") or "", next_q.get("question") or ""


def _field_for_question_category(category: str) -> str:
    return {
        "service_interest": "service_interest",
        "main_goal": "main_goal",
        "lead_source": "lead_source",
        "current_tools": "current_tools",
        "urgency": "urgency",
        "budget_signal": "budget_signal",
    }.get(category or "", "")


def _has_answer_for_category(fields: dict, category: str) -> bool:
    field = _field_for_question_category(category)
    if not field:
        return False
    if category == "current_tools":
        return bool(fields.get("current_tools") or fields.get("current_problem"))
    return bool(fields.get(field))


def _wants_human_from_text(user_text: str) -> bool:
    return sales_brain.should_handoff({}, user_text)


def _postprocess_ai_result(
    *,
    cid: str,
    wa_id: str,
    result: dict,
    ai_state: dict | None,
    user_text: str,
) -> dict:
    result = dict(result or {})
    brain_base = sales_brain.flatten_state(ai_state or {})
    state_fields = {**(((ai_state or {}).get("lead_fields") or {})), **{k: v for k, v in brain_base.items() if k != "lead_fields" and v not in (None, "", [], {})}}
    result_fields = result.get("lead_fields") if isinstance(result.get("lead_fields"), dict) else {}
    inferred = _infer_fields_from_text(user_text, ai_state, result)
    before_fields = _merge_lead_fields(state_fields, result_fields)
    merged_fields = _merge_lead_fields(before_fields, inferred)
    brain_state = sales_brain.merge_state(brain_base, merged_fields)
    if result.get("handoff"):
        brain_state = sales_brain.merge_state(brain_state, {"handoff": True, "handoff_reason": result.get("handoff_reason") or "handoff"})
    if sales_brain.should_offer_meeting(brain_state):
        brain_state = sales_brain.merge_state(
            brain_state,
            {
                "meeting_suggested": True,
                "briefing_ready": True,
                "lead_temperature": "hot" if brain_state.get("urgency") == "alta" else "warm",
            },
        )
    merged_fields = _merge_lead_fields(merged_fields, {k: v for k, v in brain_state.items() if k in sales_brain.FIELD_KEYS})
    result["lead_fields"] = merged_fields
    result["intent"] = result.get("intent") or brain_state.get("intent") or merged_fields.get("intent") or "outro"

    print(f"AI_CONTEXT_FIELDS_BEFORE cid={cid} wa_id={wa_id} fields={json.dumps(before_fields, ensure_ascii=False)[:900]}")
    print(f"AI_CONTEXT_FIELDS_AFTER cid={cid} wa_id={wa_id} fields={json.dumps(merged_fields, ensure_ascii=False)[:900]}")

    last_question = (
        merged_fields.get("last_question_asked")
        or state_fields.get("last_question_asked")
        or (ai_state or {}).get("last_question_asked")
        or (ai_state or {}).get("last_bot_message")
        or ""
    )
    reply = (result.get("reply") or "").strip()
    progress_stage = _progress_stage_for_fields(merged_fields)
    next_category, next_question = _next_question_for_fields(merged_fields)
    reply_category = sales_brain.question_category(reply) or _question_key(reply)
    last_category = (
        merged_fields.get("last_question_category")
        or state_fields.get("last_question_category")
        or (ai_state or {}).get("last_question_category")
        or _question_key(last_question)
    )
    answered_last_question = _has_answer_for_category(merged_fields, last_category)
    if next_category:
        merged_fields["next_best_question"] = next_question
    result["lead_fields"] = merged_fields

    print(f"AI_LAST_QUESTION cid={cid} wa_id={wa_id} question={last_question[:240]!r}")
    print(f"AI_PROGRESS_STAGE cid={cid} wa_id={wa_id} stage={progress_stage} next_category={next_category or '-'}")

    duplicate_goal_question = sales_brain.is_duplicate_question(reply, last_question) or (
        (sales_brain.question_category(last_question) or _question_key(last_question)) == "main_goal"
        and bool(merged_fields.get("main_goal"))
        and reply_category == "main_goal"
    )

    if duplicate_goal_question and next_question:
        print(f"AI_DUPLICATE_QUESTION_PREVENTED cid={cid} wa_id={wa_id} old_reply={reply[:240]!r} new_reply={next_question!r}")
        reply = next_question
        result["reply"] = reply
        result["next_action"] = "ask_question"

    if not duplicate_goal_question and next_question and reply_category and _has_answer_for_category(merged_fields, reply_category):
        print(f"AI_DUPLICATE_QUESTION_PREVENTED cid={cid} wa_id={wa_id} reason=answered_{reply_category} new_reply={next_question!r}")
        reply = next_question
        result["reply"] = reply
        result["next_action"] = "ask_question"

    if next_question and answered_last_question and reply_category == last_category and reply_category != next_category:
        print(f"AI_DUPLICATE_QUESTION_PREVENTED cid={cid} wa_id={wa_id} reason=answered_last_{last_category} new_reply={next_question!r}")
        reply = next_question
        result["reply"] = reply
        result["next_action"] = "ask_question"

    if next_question and next_category and reply_category not in {next_category, "offer_meeting"} and progress_stage != "encaminhar":
        print(f"AI_DUPLICATE_QUESTION_PREVENTED cid={cid} wa_id={wa_id} reason=force_progress reply_category={reply_category or '-'} new_reply={next_question!r}")
        reply = next_question
        result["reply"] = reply
        result["next_action"] = "ask_question"

    validation = sales_brain.validate_reply(result.get("reply") or "", brain_state)
    if validation.get("blocked"):
        print(
            f"AI_DUPLICATE_QUESTION_PREVENTED cid={cid} wa_id={wa_id} "
            f"reason={validation.get('reason')} new_reply={validation.get('reply')!r}"
        )
        result["reply"] = validation.get("reply") or next_question or result.get("reply")
        result["next_action"] = validation.get("next_action") or result.get("next_action") or "ask_question"
        result["lead_fields"] = _merge_lead_fields(
            result.get("lead_fields"),
            {
                "next_best_question": validation.get("question"),
                "last_question_category": validation.get("category"),
            },
        )

    if sales_brain.should_handoff(brain_state, user_text):
        result["handoff"] = True
        result["next_action"] = "handoff"
        result["handoff_reason"] = result.get("handoff_reason") or "lead_pediu_humano"
        result["lead_temperature"] = "hot"
        result["meeting_suggested"] = True
        result["briefing_ready"] = True
        result["reply"] = "Claro. Vou te encaminhar para a Julia com um resumo do que você precisa."
        briefing = result.get("briefing") if isinstance(result.get("briefing"), dict) else {}
        result["briefing"] = _merge_briefing(
            briefing,
            {
                "summary": briefing.get("summary") or _briefing_summary_from_result(result, user_text),
                "goals": [goal for goal in [merged_fields.get("desired_result") or merged_fields.get("main_goal")] if goal],
                "recommended_solution": merged_fields.get("service_interest") or result.get("intent"),
                "urgency": merged_fields.get("urgency"),
                "budget_signal": merged_fields.get("budget_signal"),
                "suggested_next_step": "Julia assumir o atendimento humano",
                "questions_to_julia": ["Confirmar prioridade, escopo e melhor horário para conversar."],
            },
        )
        print(f"HANDOFF_TRIGGERED cid={cid} wa_id={wa_id} reason=lead_pediu_humano")

    current_question = _extract_last_question(result.get("reply") or "")
    if current_question:
        current_category = sales_brain.question_category(current_question) or _question_key(current_question)
        result["lead_fields"] = _merge_lead_fields(
            result.get("lead_fields"),
            {
                "last_question_asked": current_question,
                "last_question_category": current_category,
                "next_best_question": next_question if current_question == next_question else (result.get("lead_fields") or {}).get("next_best_question"),
            },
        )
        result["last_question_category"] = current_category
        print(f"AI_NEXT_QUESTION cid={cid} wa_id={wa_id} question={current_question[:240]!r}")

    if sales_brain.should_offer_meeting(sales_brain.merge_state(brain_state, result.get("lead_fields") or {})):
        result["lead_temperature"] = "hot" if merged_fields.get("urgency") == "alta" or result.get("handoff") else "warm"
        result["meeting_suggested"] = True
        result["briefing_ready"] = True
        result["next_action"] = "offer_meeting" if not result.get("handoff") else "handoff"
        final_next = sales_brain.get_next_question(sales_brain.merge_state(brain_state, result.get("lead_fields") or {}))
        if not result.get("handoff") and final_next.get("next_action") == "offer_meeting":
            result["reply"] = final_next.get("question") or result.get("reply")
        briefing = result.get("briefing") if isinstance(result.get("briefing"), dict) else {}
        result["briefing"] = _merge_briefing(
            briefing,
            sales_brain.build_briefing(sales_brain.merge_state(brain_state, result.get("lead_fields") or {}), []),
        )
        current_question = _extract_last_question(result.get("reply") or "")
        if current_question:
            result["lead_fields"] = _merge_lead_fields(
                result.get("lead_fields"),
                {
                    "last_question_asked": current_question,
                    "last_question_category": _question_key(current_question),
                    "next_best_question": current_question,
                },
            )
            print(f"AI_NEXT_QUESTION cid={cid} wa_id={wa_id} question={current_question[:240]!r}")

    return result


def _build_panel_conversation_link(wa_id: str) -> str:
    base = (
        os.getenv("PANEL_BASE_URL")
        or os.getenv("PUBLIC_APP_URL")
        or os.getenv("FRONTEND_URL")
        or ""
    ).strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/conversations/{wa_id}"


def _briefing_summary_from_result(result: dict, fallback_text: str = "") -> str:
    briefing = (result or {}).get("briefing") or {}
    fields = (result or {}).get("lead_fields") or {}
    pieces = []
    if briefing.get("summary"):
        pieces.append(str(briefing.get("summary")).strip())
    if fields.get("current_problem"):
        pieces.append(f"Problema: {fields.get('current_problem')}")
    if fields.get("desired_result"):
        pieces.append(f"Resultado desejado: {fields.get('desired_result')}")
    if briefing.get("recommended_solution"):
        pieces.append(f"Solução recomendada: {briefing.get('recommended_solution')}")
    if not pieces and fallback_text:
        pieces.append(fallback_text.strip())
    return "\n".join([p for p in pieces if p])[:1500]


def _build_julia_briefing_message(
    *,
    wa_id: str,
    user: dict | None,
    result: dict,
    fallback_text: str = "",
) -> str:
    fields = (result or {}).get("lead_fields") or {}
    briefing = (result or {}).get("briefing") or {}
    lead_name = _format_lead_name(user, wa_id)
    phone = ((user or {}).get("telefone") or wa_id or "").strip()
    interest = fields.get("service_interest") or result.get("intent") or result.get("lead_theme") or ""
    business = fields.get("business_name") or fields.get("business_type") or ""
    problem = fields.get("current_problem") or fields.get("main_goal") or ""
    goal = fields.get("desired_result") or ", ".join(briefing.get("goals") or []) or fields.get("main_goal") or ""
    urgency = fields.get("urgency") or briefing.get("urgency") or ""
    budget = fields.get("budget_signal") or briefing.get("budget_signal") or ""
    summary = briefing.get("summary") or _briefing_summary_from_result(result, fallback_text)
    next_step = briefing.get("suggested_next_step") or result.get("next_action") or ""
    panel_link = _build_panel_conversation_link(wa_id)
    questions = briefing.get("questions_to_julia") or []
    questions_text = "\n".join([f"- {str(q).strip()}" for q in questions if str(q).strip()]) or "-"

    lines = [
        "Novo lead qualificado no Mugô Zap",
        "",
        f"Lead: {lead_name}",
        f"Telefone: {phone}",
        f"Temperatura: {result.get('lead_temperature') or ''}",
        f"Interesse: {interest}",
        f"Negócio: {business}",
        f"Problema: {problem}",
        f"Objetivo: {goal}",
        f"Urgência: {urgency}",
        f"Orçamento/sinal: {budget}",
        f"Resumo: {summary}",
        f"Próximo passo sugerido: {next_step}",
        "Perguntas para Julia:",
        questions_text,
        f"Link do painel: {panel_link or '-'}",
    ]
    return "\n".join(lines)[:3500]


async def _save_ai_result_state(
    wa_id: str,
    *,
    ai_state: dict | None,
    result: dict,
    user_text: str,
    workspace_id: str = "",
) -> dict:
    state = dict(ai_state or {})
    lead_fields = _merge_lead_fields(state.get("lead_fields"), result.get("lead_fields"))
    memory_notes = state.get("memory_notes") or []
    if not isinstance(memory_notes, list):
        memory_notes = []

    memory_entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "user": user_text[:300],
        "intent": result.get("intent") or "",
        "theme": result.get("lead_theme") or "",
        "next_action": result.get("next_action") or "",
    }

    merged = {
        **state,
        "last_user_message": user_text[:500],
        "last_user_goal": result.get("memory_goal") or user_text[:180],
        "last_question_asked": (lead_fields.get("last_question_asked") or state.get("last_question_asked") or ""),
        "last_question_category": (lead_fields.get("last_question_category") or state.get("last_question_category") or ""),
        "memory_summary": result.get("memory_summary") or user_text[:220],
        "memory_theme": result.get("memory_theme") or result.get("lead_theme") or "",
        "memory_goal": result.get("memory_goal") or user_text[:180],
        "memory_notes": (memory_notes + [memory_entry])[-8:],
        "intent": result.get("intent") or state.get("intent") or "",
        "next_action": result.get("next_action") or "",
        "meeting_suggested": bool(result.get("meeting_suggested")),
        "briefing_ready": bool(result.get("briefing_ready")),
        "handoff_reason": result.get("handoff_reason") or state.get("handoff_reason") or "",
        "service_interest": lead_fields.get("service_interest") or state.get("service_interest") or "",
        "main_goal": lead_fields.get("main_goal") or state.get("main_goal") or "",
        "desired_result": lead_fields.get("desired_result") or state.get("desired_result") or "",
        "site_scope": lead_fields.get("site_scope") or state.get("site_scope") or "",
        "lead_source": lead_fields.get("lead_source") or state.get("lead_source") or "",
        "current_tools": lead_fields.get("current_tools") or state.get("current_tools") or "",
        "current_status": lead_fields.get("current_status") or state.get("current_status") or "",
        "current_problem": lead_fields.get("current_problem") or state.get("current_problem") or "",
        "business_type": lead_fields.get("business_type") or state.get("business_type") or "",
        "business_name": lead_fields.get("business_name") or state.get("business_name") or "",
        "urgency": lead_fields.get("urgency") or state.get("urgency") or "",
        "budget_signal": lead_fields.get("budget_signal") or state.get("budget_signal") or "",
        "funnel_stage": lead_fields.get("funnel_stage") or state.get("funnel_stage") or "",
        "next_best_question": lead_fields.get("next_best_question") or state.get("next_best_question") or "",
        "handoff": bool(result.get("handoff") or state.get("handoff")),
        "lead_fields": lead_fields,
        "briefing": _merge_briefing(state.get("briefing"), result.get("briefing")),
        "follow_up": result.get("follow_up") or state.get("follow_up") or {},
        "suggested_tags": result.get("suggested_tags") or state.get("suggested_tags") or [],
        "lead_temperature": result.get("lead_temperature") or state.get("lead_temperature") or "",
    }
    return await upsert_ai_state(wa_id, merged, workspace_id=workspace_id)


async def _prepare_sales_brain_state(
    wa_id: str,
    *,
    ai_state: dict | None,
    user_text: str,
    workspace_id: str = "",
    cid: str = "",
) -> dict:
    state = sales_brain.flatten_state(ai_state or {})
    updates = sales_brain.extract_signal_from_message(user_text, state)
    state = sales_brain.merge_state(state, updates)
    next_q = sales_brain.get_next_question(state)
    if next_q.get("question"):
        state = sales_brain.merge_state(
            state,
            {
                "next_best_question": next_q.get("question"),
                "last_question_category": state.get("last_question_category") or next_q.get("category"),
                "next_action": next_q.get("next_action"),
            },
        )
    if sales_brain.should_offer_meeting(state):
        state = sales_brain.merge_state(
            state,
            {
                "meeting_suggested": True,
                "briefing_ready": True,
                "lead_temperature": "hot" if state.get("urgency") == "alta" else "warm",
                "next_action": "offer_meeting" if not state.get("handoff") else "handoff",
                "briefing": sales_brain.build_briefing(state, []),
            },
        )
    print(
        f"AI_PROGRESS_STAGE cid={cid} wa_id={wa_id} "
        f"service={state.get('service_interest') or '-'} next_category={next_q.get('category') or '-'} "
        f"updates={json.dumps(updates, ensure_ascii=False)[:700]}"
    )
    return await upsert_ai_state(wa_id, state, workspace_id=workspace_id)


def _should_trigger_internal_briefing(result: dict) -> bool:
    return bool(result.get("handoff") or result.get("briefing_ready") or result.get("next_action") == "handoff")


def _is_human_service_choice(result: dict, user_text: str = "") -> bool:
    text = (user_text or "").strip().lower()
    return (
        (result or {}).get("intent") == "humano"
        or text in {"6", "06", "falar com equipe", "falar com a equipe"}
    )


async def _handle_ai_operational_decision(
    *,
    wa_id: str,
    cid: str,
    result: dict,
    user_text: str,
    user: dict | None,
    workspace_id: str = "",
) -> bool:
    if not _should_trigger_internal_briefing(result):
        return False

    state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
    wants_handoff = bool(result.get("handoff") or result.get("next_action") == "handoff")
    if wants_handoff and state.get("handoff_sent_at"):
        print(f"[{cid}] HANDOFF:skip_duplicate wa_id={wa_id} handoff_sent_at={state.get('handoff_sent_at')}")
        return True
    if not wants_handoff and state.get("briefing_sent_at"):
        print(f"[{cid}] BRIEFING:skip_duplicate wa_id={wa_id} briefing_sent_at={state.get('briefing_sent_at')}")
        return True

    fields = result.get("lead_fields") or {}
    topic = (
        fields.get("service_interest")
        or result.get("intent")
        or result.get("lead_theme")
        or "Atendimento Mugô"
    )
    summary = _briefing_summary_from_result(result, user_text) or user_text
    internal_briefing = _build_julia_briefing_message(
        wa_id=wa_id,
        user=user,
        result=result,
        fallback_text=user_text,
    )
    now = _now_iso()

    if wants_handoff:
        print(
            "HANDOFF_TRIGGERED "
            f"cid={cid} wa_id={wa_id} topic={topic} reason={result.get('handoff_reason') or result.get('next_action')}"
        )
        print(f"[{cid}] HANDOFF:start wa_id={wa_id} topic={topic} summary_len={len(summary)}")
        start_handoff_now(
            wa_id=wa_id,
            cid=cid,
            reason="ai_handoff",
            topic=topic,
            summary=summary,
            last_text=user_text,
            user=user,
            workspace_id=workspace_id,
            internal_briefing=internal_briefing,
        )
        await mark_handoff_done(wa_id, topic=topic, summary=summary, workspace_id=workspace_id)
        latest = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        await upsert_ai_state(
            wa_id,
            {
                **latest,
                "briefing_sent_at": latest.get("briefing_sent_at") or now,
                "handoff_sent_at": latest.get("handoff_sent_at") or now,
            },
            workspace_id=workspace_id,
        )
        return True

    print(f"[{cid}] BRIEFING:send_internal wa_id={wa_id} topic={topic} summary_len={len(summary)}")
    julia_ok = safe_send(
        HUMAN_NUMBER,
        internal_briefing,
        meta={"event": "internal_briefing_to_julia", "cid": cid, "lead_wa_id": wa_id, "topic": topic},
        workspace_id=workspace_id,
        cid=cid,
    )
    eduarda_ok = safe_send(
        EDUARDA_NUMBER,
        internal_briefing,
        meta={"event": "internal_briefing_to_eduarda", "cid": cid, "lead_wa_id": wa_id, "topic": topic},
        workspace_id=workspace_id,
        cid=cid,
    )
    latest = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
    await upsert_ai_state(
        wa_id,
        {
            **latest,
            "briefing_sent_at": latest.get("briefing_sent_at") or now,
            "briefing_sent_julia": bool(julia_ok),
            "briefing_sent_eduarda": bool(eduarda_ok),
        },
        workspace_id=workspace_id,
    )

    try:
        create_task(
            wa_id,
            f"Revisar briefing qualificado: {topic}",
            datetime.now(timezone.utc).isoformat(),
            workspace_id=workspace_id,
        )
    except Exception as e:
        print(f"[{cid}] Falha ao criar task de briefing:", repr(e))

    print(
        "BRIEFING_SENT "
        f"cid={cid} wa_id={wa_id} julia_ok={bool(julia_ok)} eduarda_ok={bool(eduarda_ok)} topic={topic}"
    )
    return bool(julia_ok or eduarda_ok)


def _display_name(user_row: Optional[dict], incoming_name: str, telefone: str, wa_id: str) -> str:
    saved_name = ((user_row or {}).get("name") or "").strip()
    incoming_name = (incoming_name or "").strip()
    telefone = (telefone or "").strip()
    wa_id = (wa_id or "").strip()
    return incoming_name or saved_name or telefone or wa_id


def _format_lead_name(user: dict | None, wa_id: str) -> str:
    user = user or {}
    name = (
        (user.get("name") or "").strip()
        or (user.get("contact_name") or "").strip()
        or (user.get("profile_name") or "").strip()
        or (user.get("telefone") or "").strip()
        or (wa_id or "").strip()
    )
    return name or "Lead sem nome"


def _infer_entry_type(source: str, campaign: str, msg_type: str) -> str:
    source = (source or "").strip().lower()
    campaign = (campaign or "").strip().lower()
    msg_type = (msg_type or "").strip().lower()

    paid_tokens = {
        "meta_ads", "google_ads", "tiktok_ads", "pinterest_ads",
        "trafego_pago", "ads", "paid"
    }

    if source in paid_tokens:
        return "paid"

    if any(k in campaign for k in ["ads", "camp", "meta", "google", "trafego"]):
        return "paid"

    if source in {"indicacao", "organico", "whatsapp", "instagram", "facebook"}:
        return "organic"

    if msg_type == "interactive":
        return "organic"

    return "organic"


def _infer_attendance_mode(source: str, campaign: str) -> str:
    entry_type = _infer_entry_type(source, campaign, "")

    if entry_type == "paid":
        return "bot"

    if entry_type == "client":
        return "human"

    return "hybrid"


def _resolve_operation_status(user: dict | None) -> str:
    user = user or {}

    flow_data = user.get("flow_data") or {}
    if isinstance(flow_data, str):
        try:
            flow_data = json.loads(flow_data)
        except Exception:
            flow_data = {}

    flow_status = str((flow_data or {}).get("bot_status") or "").strip().lower()
    attendance_mode = ((user.get("attendance_mode") or "")).strip().lower()
    automation_paused = bool(user.get("automation_paused"))
    bot_enabled = bool(user.get("bot_enabled", True))
    handoff_active = bool(user.get("handoff_active"))
    handoff_at = (user.get("handoff_at") or "").strip()

    if flow_status in {"bot_active", "ai_active", "human_active", "handoff_pending", "handoff_active", "paused", "followup_scheduled", "resume_ready", "closed"}:
        return flow_status

    if handoff_active or handoff_at:
        return "handoff"

    if attendance_mode == "human":
        return "human_active"

    if automation_paused:
        return "automation_paused"

    if bot_enabled:
        return "bot_active"

    return "manual"


def _enrich_conversation_item(item: dict | None) -> dict:
    row = dict(item or {})
    row["operation_status"] = _resolve_operation_status(row)
    return row


def _enrich_conversation_items(items: List[dict]) -> List[dict]:
    return [_enrich_conversation_item(item) for item in (items or [])]


async def _dedupe_incoming(wa_id: str, message_id: str, cid: str) -> bool:
    if not wa_id or not message_id:
        return False

    try:
        ai_state = await get_ai_state(wa_id) or {}
        last_id = (ai_state.get("last_in_msg_id") or "").strip()
        if last_id and last_id == message_id:
            if DEBUG_WEBHOOK:
                print(f"[{cid}] DEDUPE HIT -> wa_id={wa_id} msg_id={message_id}")
            return True

        await upsert_ai_state(
            wa_id,
            {"last_in_msg_id": message_id, "last_in_at": datetime.now(timezone.utc).isoformat()},
        )
        return False
    except Exception as e:
        if DEBUG_WEBHOOK:
            print(f"[{cid}] DEDUPE WARN:", repr(e))
        return False


def _extract_log_text(payload: Union[str, Dict[str, Any]]) -> str:
    if isinstance(payload, str):
        return (payload or "").strip()
    if not isinstance(payload, dict):
        return ""

    ptype = (payload.get("type") or "").lower().strip()
    if ptype in ("text", "buttons", "list"):
        return (payload.get("text") or "").strip()

    if "text" in payload and isinstance(payload.get("text"), dict):
        return (payload["text"].get("body") or "").strip()

    if "interactive" in payload and isinstance(payload.get("interactive"), dict):
        inter = payload.get("interactive") or {}
        body = inter.get("body") or {}
        if isinstance(body, dict):
            return (body.get("text") or "").strip()

    return (payload.get("body") or "").strip()


def safe_send(
    to_wa_id: str,
    payload: Union[str, Dict[str, Any]],
    *,
    meta: Optional[dict] = None,
    workspace_id: str = "",
    cid: str = "",
) -> bool:
    if not to_wa_id:
        return False

    log_text = _extract_log_text(payload)
    if not log_text:
        return False
    ptype = (payload.get("type") or "text").strip().lower() if isinstance(payload, dict) else "text"
    print(f"[{cid}] SAFE_SEND:attempt to={to_wa_id} type={ptype} text_len={len(log_text)} meta_event={(meta or {}).get('event') or (meta or {}).get('src') or '-'}")

    try:
        send_message(to_wa_id, payload)

        try:
            log_message(to_wa_id, "out", log_text, meta=meta or {}, workspace_id=workspace_id)
        except Exception as e:
            print(f"[{cid}] log_message(out) failed:", repr(e))

        print(f"[{cid}] SAFE_SEND:ok to={to_wa_id} type={ptype} text_preview={log_text[:160]!r}")
        return True

    except Exception as e:
        print(f"[{cid}] SAFE_SEND:fail to={to_wa_id} type={ptype} error={repr(e)}")

        if isinstance(payload, dict) and ptype in {"buttons", "list"}:
            fallback_text = _menu_fallback_text()
            try:
                print(f"[{cid}] SAFE_SEND:fallback_text_attempt to={to_wa_id} original_type={ptype}")
                send_message(to_wa_id, fallback_text)
                log_message(
                    to_wa_id,
                    "out",
                    fallback_text,
                    meta={"event": "interactive_fallback_text", "cid": cid, "original_type": ptype, **(meta or {})},
                    workspace_id=workspace_id,
                )
                print(f"[{cid}] SAFE_SEND:fallback_text_ok to={to_wa_id}")
                return True
            except Exception as fallback_error:
                print(f"[{cid}] SAFE_SEND:fallback_text_fail to={to_wa_id} error={repr(fallback_error)}")

        try:
            log_message(
                to_wa_id,
                "out",
                f"[ERRO ENVIO] {log_text[:500]}",
                meta={
                    "event": "send_fail",
                    "cid": cid,
                    "error": str(e),
                    **(meta or {}),
                },
                workspace_id=workspace_id,
            )
        except Exception:
            pass

        return False


def _normalize_source_from_text(text: str) -> str:
    text = (text or "").strip().lower()
    if not text:
        return ""
    if "meta" in text or "instagram" in text or "facebook" in text:
        return "meta_ads"
    if "google" in text:
        return "google_ads"
    if "indica" in text:
        return "indicacao"
    if "org" in text:
        return "organico"
    return text[:80]


def _extract_source_campaign_from_message(msg: dict, text: str) -> dict:
    source = ""
    campaign = ""

    try:
        context = (msg.get("context") or {})
        referred = (context.get("referred_product") or {})
        source = (context.get("from") or "").strip()
        campaign = (referred.get("catalog_id") or "").strip()
    except Exception:
        pass

    normalized = _normalize_source_from_text(text)
    if normalized and not source:
        source = normalized

    return {
        "source": source[:120] if source else "",
        "campaign": campaign[:160] if campaign else "",
    }


async def _supabase_delete(table: str, column: str, value: str, workspace_id: str = ""):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase env not configured")

    async with httpx.AsyncClient(timeout=20) as client:
        params = {
            "workspace_id": f"eq.{resolve_workspace_id(explicit_workspace_id=workspace_id)}",
            column: f"eq.{value}",
        }
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Prefer": "return=representation",
        }
        resp = await client.delete(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=headers)

        if resp.status_code >= 300 and "workspace_id" in (resp.text or "").lower():
            resp = await client.delete(
                f"{SUPABASE_URL}/rest/v1/{table}",
                params={column: f"eq.{value}"},
                headers=headers,
            )

    if resp.status_code >= 300:
        raise Exception(f"{table}.{column} -> {resp.status_code} :: {resp.text}")

    try:
        return resp.json()
    except Exception:
        return []


async def _supabase_exists(table: str, column: str, value: str, workspace_id: str = "") -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase env not configured")

    params = {
        "select": column,
        column: f"eq.{value}",
        "limit": "1",
        "workspace_id": f"eq.{resolve_workspace_id(explicit_workspace_id=workspace_id)}",
    }
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=headers)
        if resp.status_code >= 300 and "workspace_id" in (resp.text or "").lower():
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{table}",
                params={"select": column, column: f"eq.{value}", "limit": "1"},
                headers=headers,
            )

    if resp.status_code >= 300:
        raise Exception(f"{table}.{column} exists -> {resp.status_code} :: {resp.text}")

    try:
        rows = resp.json() or []
        return bool(rows)
    except Exception:
        return False


async def delete_conversation_bundle(wa_id: str, deleted_by: str = "", workspace_id: str = "") -> dict:
    wa_id = (wa_id or "").strip()
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id)
    if not wa_id:
        raise HTTPException(status_code=400, detail="Missing wa_id")

    deleted = {}
    errors = {}
    remaining = {}

    targets = [
        ("conversations", SUPABASE_TABLE_CONVERSATIONS, "wa_id"),
        ("messages", WA_MESSAGES_TABLE, "wa_id"),
        ("tasks", WA_TASKS_TABLE, "wa_id"),
        ("ai_state", SUPABASE_TABLE_AI_STATE, "wa_id"),
        ("flow_state", SUPABASE_TABLE_FLOW_STATE, "wa_id"),
        ("users", WA_USERS_TABLE, "wa_id"),
    ]

    for label, table, column in targets:
        try:
            rows = await _supabase_delete(table, column, wa_id, workspace_id=workspace_id)
            deleted[label] = len(rows or [])
            still_exists = await _supabase_exists(table, column, wa_id, workspace_id=workspace_id)
            remaining[label] = still_exists
            if still_exists:
                errors[label] = f"{table} ainda possui registro(s) para {wa_id}"
        except Exception as e:
            errors[label] = str(e)

    return {
        "wa_id": wa_id,
        "workspace_id": workspace_id,
        "deleted_by": deleted_by,
        "deleted": deleted,
        "remaining": remaining,
        "errors": errors,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "env_path": str(ENV_PATH),
        "supabase_ok": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY),
    }


@app.get("/api/me")
async def api_me(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    return {"ok": True, "user": user}


@app.get("/api/debug/ai-state/{wa_id}")
async def api_debug_ai_state(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    state = await get_ai_state(wa_id, workspace_id=user.get("workspace_id"))
    return {"ok": True, "wa_id": wa_id, "state": state}


@app.get("/api/debug/meta-env")
async def api_debug_meta_env(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    env = meta_env_status()
    return {
        "whatsapp_token_present": env["whatsapp_token_present"],
        "whatsapp_phone_number_id": env["whatsapp_phone_number_id"] or "missing",
        "whatsapp_verify_token_present": env["whatsapp_verify_token_present"],
    }


@app.post("/api/debug/send-test-whatsapp/{wa_id}")
async def api_debug_send_test_whatsapp(
    wa_id: str,
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    payload = await request.json()
    message = (payload.get("message") or "teste").strip() or "teste"
    try:
        result = send_message_detailed(wa_id, message, raise_for_status=False)
        return {
            "ok": bool(result.get("ok")),
            "status_code": result.get("status_code"),
            "body": result.get("body"),
            "phone_number_id": result.get("phone_number_id"),
        }
    except Exception as e:
        env = meta_env_status()
        return {
            "ok": False,
            "status_code": None,
            "body": f"{type(e).__name__}: {str(e)[:500]}",
            "phone_number_id": env.get("whatsapp_phone_number_id") or "missing",
        }


@app.get("/api/debug/lead-state/{wa_id}")
async def api_debug_lead_state(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")
    ai_state = await get_ai_state(wa_id, workspace_id=workspace_id)
    flat_state = sales_brain.flatten_state(ai_state)
    messages = get_recent_messages(wa_id, limit=20, workspace_id=workspace_id) or []
    conversations = list_conversations(limit=500, workspace_id=workspace_id) or []
    lead_row = next((item for item in conversations if str(item.get("wa_id") or "") == str(wa_id)), {})

    return {
        "ok": True,
        "wa_id": wa_id,
        "ai_state": ai_state,
        "service_interest": flat_state.get("service_interest"),
        "intent": flat_state.get("intent") or ai_state.get("memory_theme") or "",
        "main_goal": flat_state.get("main_goal"),
        "desired_result": flat_state.get("desired_result"),
        "site_scope": flat_state.get("site_scope"),
        "lead_source": flat_state.get("lead_source"),
        "current_tools": flat_state.get("current_tools"),
        "current_problem": flat_state.get("current_problem"),
        "business_type": flat_state.get("business_type"),
        "urgency": flat_state.get("urgency"),
        "budget_signal": flat_state.get("budget_signal"),
        "funnel_stage": flat_state.get("funnel_stage"),
        "last_question_asked": flat_state.get("last_question_asked"),
        "last_question_category": flat_state.get("last_question_category"),
        "next_best_question": flat_state.get("next_best_question"),
        "meeting_suggested": bool(flat_state.get("meeting_suggested")),
        "briefing_ready": bool(flat_state.get("briefing_ready")),
        "handoff": bool(flat_state.get("handoff")),
        "handoff_reason": flat_state.get("handoff_reason") or "",
        "recent_messages": messages,
        "tags": lead_row.get("tags") or ai_state.get("suggested_tags") or [],
        "lead_temperature": ai_state.get("lead_temperature") or lead_row.get("lead_temperature") or "",
        "next_action": ai_state.get("next_action") or "",
        "lead_fields": ai_state.get("lead_fields") or {},
        "briefing": ai_state.get("briefing") or {},
        "follow_up": ai_state.get("follow_up") or {},
        "suggested_tags": ai_state.get("suggested_tags") or [],
        "briefing_sent_at": ai_state.get("briefing_sent_at") or "",
        "handoff_sent_at": ai_state.get("handoff_sent_at") or "",
    }


@app.post("/api/debug/reset-lead/{wa_id}")
async def api_debug_reset_lead(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")
    reset = []
    await reset_ai_state(wa_id, workspace_id=workspace_id)
    reset.append("ai_state")
    try:
        clear_flow(wa_id, workspace_id=workspace_id)
        reset.append("flow_state")
    except Exception as e:
        print(f"DEBUG_RESET_LEAD clear_flow failed wa_id={wa_id} error={repr(e)}")
    try:
        clear_handoff(wa_id, workspace_id=workspace_id)
        set_handoff_pending(wa_id, False, workspace_id=workspace_id)
        upsert_user(
            wa_id,
            workspace_id=workspace_id,
            bot_enabled=True,
            automation_paused=False,
            handoff_active=False,
            handoff_pending=False,
            attendance_mode="bot",
        )
        reset.append("handoff_flags")
    except Exception as e:
        print(f"DEBUG_RESET_LEAD handoff flags failed wa_id={wa_id} error={repr(e)}")
    return {"ok": True, "wa_id": wa_id, "reset": reset}


@app.post("/api/debug/simulate-incoming/{wa_id}")
async def api_debug_simulate_incoming(
    wa_id: str,
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    auth_user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = auth_user.get("workspace_id")
    payload = await request.json()
    button_id = (payload.get("button_id") or payload.get("choice_id") or "").strip()
    service_ctx = service_choice_context(button_id) if button_id else {}
    text = (payload.get("message") or payload.get("text") or service_ctx.get("label") or button_id).strip()
    name = (payload.get("name") or "Lead Teste").strip()
    source = (payload.get("source") or "").strip()
    campaign = (payload.get("campaign") or "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    cid = uuid.uuid4().hex[:10]
    entry_type = _infer_entry_type(source, campaign, "text")
    attendance_mode = _infer_attendance_mode(source, campaign)

    user = upsert_user(
        wa_id,
        name=name,
        telefone=wa_id,
        workspace_id=workspace_id,
        assigned_to=DEFAULT_ASSIGNEE,
        stage="Novo",
        lead_stage="novo",
        source=source or None,
        last_source=source or None,
        campaign=campaign or None,
        entry_type=entry_type,
        inbound_type=entry_type,
        attendance_mode=attendance_mode,
    )

    resolved_name = _display_name(user, name, wa_id, wa_id)

    log_message(
        wa_id,
        "in",
        text,
        meta={"src": "debug_simulated_incoming", "cid": cid, "source": source, "campaign": campaign, "button_id": button_id},
        workspace_id=workspace_id,
    )

    selected_choice = button_id or (text if is_service_choice(text) else "")
    if selected_choice and is_service_choice(selected_choice):
        service_ctx = apply_service_choice(wa_id, selected_choice, workspace_id=workspace_id)
        try:
            mark_first_message_sent(wa_id, workspace_id=workspace_id)
        except Exception:
            pass
        current_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        brain_updates = sales_brain.service_choice_update(selected_choice)
        brain_state = sales_brain.merge_state(current_state, brain_updates)
        await upsert_ai_state(
            wa_id,
            {
                **brain_state,
                "selected_service_id": service_ctx.get("id"),
                "selected_service": service_ctx.get("service_interest"),
                "service_interest": service_ctx.get("service_interest"),
                "intent": service_ctx.get("intent") or brain_state.get("intent") or "",
                "lead_fields": _merge_lead_fields(
                    brain_state.get("lead_fields"),
                    {
                        "service_interest": service_ctx.get("service_interest"),
                        "intent": service_ctx.get("intent"),
                        "funnel_stage": "qualificacao",
                        "last_question_asked": brain_updates.get("last_question_asked"),
                        "last_question_category": brain_updates.get("last_question_category"),
                        "next_best_question": brain_updates.get("next_best_question"),
                    },
                ),
            },
            workspace_id=workspace_id,
        )
        text = service_ctx.get("label") or text

    if not bool(user.get("first_message_sent")) and not selected_choice and text.lower() in {"oi", "oie", "olá", "ola", "opa", "start", "menu"}:
        flow_start = handle_mugo_flow(wa_id, "start", choice_id="", workspace_id=workspace_id)
        if flow_start:
            try:
                mark_first_message_sent(wa_id, workspace_id=workspace_id)
            except Exception:
                pass
            log_message(
                wa_id,
                "out",
                _extract_log_text(flow_start),
                meta={"src": "debug_flow_start", "cid": cid},
                workspace_id=workspace_id,
            )
            return {"ok": True, "wa_id": wa_id, "flow_response": flow_start}

    recent_messages = get_recent_messages(wa_id, limit=12, workspace_id=workspace_id) or []
    lead_context = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
    lead_context = await _prepare_sales_brain_state(
        wa_id,
        ai_state=lead_context,
        user_text=text,
        workspace_id=workspace_id,
        cid=cid,
    )

    result = await generate_reply(
        wa_id=wa_id,
        user_message=text,
        first_message_sent=True,
        name=resolved_name,
        telefone=wa_id,
        recent_messages=recent_messages,
        lead_context=lead_context,
    )
    result = _postprocess_ai_result(
        cid=cid,
        wa_id=wa_id,
        result=result,
        ai_state=lead_context,
        user_text=text,
    )

    try:
        set_tags(wa_id, _extract_auto_tags(result), workspace_id=workspace_id)
    except Exception:
        pass

    try:
        ai_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        await _save_ai_result_state(
            wa_id,
            ai_state=ai_state,
            result=result,
            user_text=text,
            workspace_id=workspace_id,
        )
    except Exception as e:
        print(f"[{cid}] Falha ao salvar memória da IA:", repr(e))

    reply_text = (result.get("reply") or "").strip() or "Em uma frase: qual é o foco agora?"
    log_message(
        wa_id,
        "out",
        reply_text,
        meta={"src": "debug_ai_reply", "cid": cid},
        workspace_id=workspace_id,
    )

    await _handle_ai_operational_decision(
        wa_id=wa_id,
        cid=cid,
        result=result,
        user_text=text,
        user=user,
        workspace_id=workspace_id,
    )

    return {
        "ok": True,
        "wa_id": wa_id,
        "reply": reply_text,
        "result": result,
    }


@app.get("/api/conversations")
async def api_conversations(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    items = list_conversations(limit=200, workspace_id=user.get("workspace_id")) or []
    enriched = _enrich_conversation_items(items)
    return {"ok": True, "items": enriched}


@app.delete("/api/conversations/{wa_id}")
async def api_delete_conversation(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )

    result = await delete_conversation_bundle(
        wa_id=wa_id,
        deleted_by=user.get("email") or user.get("name") or "unknown",
        workspace_id=user.get("workspace_id"),
    )

    print("DELETE_CONVERSATION_RESULT:", json.dumps(result, ensure_ascii=False))

    if result.get("errors"):
        raise HTTPException(status_code=409, detail=result)

    return {"ok": True, "result": result}


@app.get("/api/messages")
async def api_messages(
    wa_id: str = Query(...),
    limit: int = Query(40),
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    msgs = get_recent_messages(wa_id, limit=int(limit), workspace_id=user.get("workspace_id")) or []
    print(
        "API_MESSAGES:",
        json.dumps(
            {
                "wa_id": wa_id,
                "workspace_id": user.get("workspace_id"),
                "limit": int(limit),
                "count": len(msgs),
                "last_created_at": (msgs[-1].get("created_at") if msgs else None),
            },
            ensure_ascii=False,
        ),
    )
    return {"ok": True, "items": msgs}


@app.get("/api/conversations/{wa_id}")
async def api_conversation_detail(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    msgs = get_recent_messages(wa_id, limit=200, workspace_id=user.get("workspace_id")) or []
    return {"ok": True, "messages": msgs}


@app.post("/api/conversations/{wa_id}/send")
async def api_send_message(
    wa_id: str,
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")
    payload = await request.json()
    text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    try:
        _apply_operational_state(
            wa_id,
            workspace_id=workspace_id,
            status="human_active",
            waiting_for="human",
            user_patch={
                "attendance_mode": "human",
                "automation_paused": True,
                "bot_enabled": False,
                "human_owner": user.get("name") or user.get("email") or DEFAULT_ASSIGNEE,
            },
            flow_patch={
                "last_human_text": _trim_text(text),
                "last_human_at": _now_iso(),
            },
            event="state_change",
        )
    except Exception:
        pass

    ok = safe_send(
        wa_id,
        text,
        meta={"src": "panel_manual_send", "by": user.get("email")},
        workspace_id=workspace_id,
    )
    return {"ok": ok}


@app.post("/api/conversations/{wa_id}/handoff/close")
async def api_close_handoff(
    wa_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")
    flow_data = _flow_data(wa_id, workspace_id=workspace_id)
    ai_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
    context_summary = (
        (flow_data.get("context_summary") or "").strip()
        or (ai_state.get("handoff_summary") or "").strip()
        or (flow_data.get("briefing") or "").strip()
        or (ai_state.get("memory_summary") or "").strip()
    )

    clear_handoff(wa_id, workspace_id=workspace_id)

    try:
        set_handoff_pending(wa_id, False, workspace_id=workspace_id)
    except Exception:
        pass

    try:
        _apply_operational_state(
            wa_id,
            workspace_id=workspace_id,
            status="resume_ready",
            step=(flow_data.get("current_step") or "ai_resume"),
            waiting_for="customer",
            user_patch={
                "attendance_mode": "hybrid",
                "automation_paused": False,
                "bot_enabled": True,
                "handoff_active": False,
            },
            flow_patch={
                "handoff_closed_at": _now_iso(),
                "resumed_at": _now_iso(),
            },
            event="handoff_close",
        )
    except Exception:
        pass

    try:
        merge_flow_data(
            wa_id,
            {
                "bot_paused": False,
                "waiting_after_handoff": False,
                "bot_status": "resume_ready",
                "resume_mode": "awaiting_customer_after_handoff",
                "last_handoff_closed_at": _now_iso(),
                "current_step": (flow_data.get("current_step") or "ai_resume"),
                "flow_step": (flow_data.get("current_step") or "ai_resume"),
                "context_summary": context_summary[:900],
            },
            workspace_id=workspace_id,
        )
    except Exception:
        pass

    return {"ok": True}


@app.patch("/api/conversations/{wa_id}")
async def api_update_contact(
    wa_id: str,
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")

    allowed = {
        "name": str,
        "telefone": str,
        "stage": str,
        "lead_stage": str,
        "notes": str,
        "tags": list,
        "owner": str,
        "assigned_to": str,
        "source": str,
        "last_source": str,
        "campaign": str,
        "entry_type": str,
        "inbound_type": str,
        "attendance_mode": str,
        "human_owner": str,
        "automation_paused": bool,
        "bot_enabled": bool,
        "handoff_active": bool,
        "closed_at": str,
    }
    data = {}
    for key in allowed:
        if key in payload and payload[key] is not None:
            data[key] = payload[key]

    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "stage" not in data:
        data["stage"] = "Novo"

    if "lead_stage" not in data and data.get("stage"):
        data["lead_stage"] = str(data["stage"]).strip().lower()

    upsert_user(wa_id, workspace_id=user.get("workspace_id"), **data)
    return {"ok": True}


@app.get("/api/tasks")
async def api_list_tasks(
    status: str = Query("open"),
    due_before: Optional[str] = Query(None),
    wa_id: Optional[str] = Query(None),
    limit: int = Query(200),
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    items = list_tasks(
        status=status or "",
        due_before=due_before,
        wa_id=wa_id,
        limit=int(limit) or 200,
        workspace_id=user.get("workspace_id"),
    )
    return {"ok": True, "items": items}


@app.post("/api/tasks")
async def api_create_task(
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")

    wa_id = (payload.get("wa_id") or "").strip()
    title = (payload.get("title") or "").strip()
    due_at = (payload.get("due_at") or "").strip()
    if not wa_id or not title or not due_at:
        raise HTTPException(status_code=400, detail="Missing wa_id/title/due_at")

    item = create_task(wa_id, title, due_at, workspace_id=workspace_id)

    try:
        upsert_user(
            wa_id,
            workspace_id=workspace_id,
            stage="Qualificado",
            lead_stage="qualificado",
            qualified_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        pass

    return {"ok": True, "item": item}


@app.post("/api/tasks/{task_id}/done")
async def api_done_task(
    task_id: str,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    res = done_task(task_id, workspace_id=user.get("workspace_id"))
    return {"ok": res.get("ok", False), "item": res.get("item")}


@app.patch("/api/tasks/{task_id}")
async def api_update_task(
    task_id: str,
    request: Request,
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")

    allowed_keys = {"due_at", "title", "status", "wa_id"}
    fields = {k: v for k, v in payload.items() if k in allowed_keys and v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = update_task(task_id, workspace_id=user.get("workspace_id"), **fields)
    return {"ok": res.get("ok", False), "item": res.get("item")}


@app.get("/api/dashboard/summary")
async def api_dashboard_summary(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    workspace_id = user.get("workspace_id")

    items = _enrich_conversation_items(list_conversations(limit=500, workspace_id=workspace_id) or [])
    tasks = list_tasks(status="open", limit=500, workspace_id=workspace_id) or []

    now_iso = datetime.now(timezone.utc).isoformat()

    leads_by_source: Dict[str, int] = {}
    leads_by_entry_type: Dict[str, int] = {}
    leads_by_status: Dict[str, int] = {}
    handoffs_pending = 0
    conversations_open = 0
    waiting_human = 0
    bot_active = 0
    paused_automation = 0
    urgent_tasks = 0

    for item in items:
        row = item or {}
        source = ((row.get("source") or row.get("last_source") or "sem_origem")).strip() or "sem_origem"
        entry_type = ((row.get("entry_type") or row.get("inbound_type") or "unknown")).strip() or "unknown"
        status = (row.get("operation_status") or "manual").strip()

        leads_by_source[source] = leads_by_source.get(source, 0) + 1
        leads_by_entry_type[entry_type] = leads_by_entry_type.get(entry_type, 0) + 1
        leads_by_status[status] = leads_by_status.get(status, 0) + 1

        if status in {"handoff", "handoff_pending", "handoff_active"}:
            handoffs_pending += 1

        if status == "human_active":
            waiting_human += 1

        if status in {"bot_active", "ai_active", "resume_ready"}:
            bot_active += 1

        if status in {"automation_paused", "paused"}:
            paused_automation += 1

        conversations_open += 1

    for task in tasks:
        due_at = (task.get("due_at") or "").strip()
        if due_at and due_at <= now_iso:
            urgent_tasks += 1

    return {
        "ok": True,
        "summary": {
            "conversations_open": conversations_open,
            "handoffs_pending": handoffs_pending,
            "waiting_human": waiting_human,
            "bot_active": bot_active,
            "paused_automation": paused_automation,
            "urgent_tasks": urgent_tasks,
            "leads_by_source": leads_by_source,
            "leads_by_entry_type": leads_by_entry_type,
            "leads_by_status": leads_by_status,
        },
    }


@app.post("/api/followups/run")
async def api_run_followups(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
    x_workspace_id: str = Header(None, alias="X-Workspace-Id"),
):
    user = await get_current_user(
        authorization=authorization,
        x_panel_key=x_panel_key,
        x_workspace_id=x_workspace_id,
    )
    result = await process_followups(workspace_id=user.get("workspace_id"))
    return result


@app.get("/events")
async def sse_events(token: str = Query(""), workspace_id: str = Query("")):
    token = (token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    user = await _supabase_get_user(token)
    if not _is_allowed_internal_user(user):
        raise HTTPException(status_code=403, detail="User not allowed in internal panel")

    resolved_workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id, user=user)

    async def event_gen():
        yield "event: ready\ndata: ok\n\n"

        while True:
            try:
                items = list_conversations(limit=200, workspace_id=resolved_workspace_id) or []
                enriched = _enrich_conversation_items(items)
                payload = json.dumps({"type": "conversations", "items": enriched}, ensure_ascii=False)
                yield f"event: conversations\ndata: {payload}\n\n"
            except Exception as e:
                err = json.dumps({"type": "error", "detail": str(e)}, ensure_ascii=False)
                yield f"event: error\ndata: {err}\n\n"

            await asyncio.sleep(6)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


async def mark_handoff_done(wa_id: str, topic: str = "", summary: str = "", workspace_id: str = ""):
    try:
        existing_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        await upsert_ai_state(
            wa_id,
            {
                **existing_state,
                "handoff_done": True,
                "handoff_done_at": datetime.now(timezone.utc).isoformat(),
                "handoff_topic": (topic or "").strip()[:120],
                "handoff_summary": (summary or "").strip()[:900],
                "handoff_sent_at": existing_state.get("handoff_sent_at") or datetime.now(timezone.utc).isoformat(),
            },
            workspace_id=workspace_id,
        )
        merge_flow_data(
            wa_id,
            {
                "topic": (topic or "").strip()[:120],
                "context_summary": (summary or "").strip()[:900],
                "bot_status": "handoff_active",
                "resume_mode": "",
                "flow_step": "handoff_waiting",
                "handoff_closed_at": _now_iso(),
            },
            workspace_id=workspace_id,
        )
        print(f"FLOW:handoff_close wa_id={wa_id} status=handoff_active step=handoff_waiting")
    except Exception:
        pass


def _build_handoff_link(topic: str, wa_id: str, summary: str, user: dict | None = None) -> str:
    topic = (topic or "Atendimento Mugô").strip()
    summary = (summary or "").strip()
    lead_name = _format_lead_name(user, wa_id)

    link_text = (
        f"Olá Julia! Meu nome é {lead_name} e estou interessado em {topic}.\n\n"
        f"ID: {wa_id}\n"
        f"Frente: {topic}\n\n"
        "Briefing:\n"
        f"{summary}"
    )
    encoded_text = urllib.parse.quote(link_text)
    return f"https://wa.me/{HUMAN_NUMBER}?text={encoded_text}"


def start_handoff_now(
    *,
    wa_id: str,
    cid: str,
    reason: str,
    topic: str = "",
    summary: str = "",
    last_text: str = "",
    user: dict | None = None,
    workspace_id: str = "",
    internal_briefing: str = "",
):
    topic = (topic or "Atendimento Mugô").strip()[:100]
    flow_data = _flow_data(wa_id, workspace_id=workspace_id)

    if flow_data.get("bot_paused") and flow_data.get("waiting_after_handoff"):
        print(f"[{cid}] Handoff já pausado para {wa_id}; ignorando reenvio.")
        return

    if topic.lower() in {"encaminhado pela ia (debug)", "encaminhado pela ia"}:
        topic = "Atendimento Mugô"

    reason_label_map = {
        "flow_completed": "Briefing concluído",
        "ai_handoff": "Lead qualificado",
        "debug_ai_handoff": "Lead qualificado",
    }
    reason_label = reason_label_map.get((reason or "").strip(), "Lead qualificado")

    lead_name = _format_lead_name(user, wa_id)

    try:
        set_handoff_pending(wa_id, False, workspace_id=workspace_id)
        set_handoff_topic(wa_id, topic, workspace_id=workspace_id)
    except Exception as e:
        print(f"[{cid}] Falha ao atualizar status de handoff: {e}")

    if not summary:
        try:
            hist = get_recent_messages(wa_id, limit=10, workspace_id=workspace_id) or []
            entradas = [(m.get("text") or "").strip() for m in hist if m.get("direction") == "in"]
            summary = " | ".join(entradas[-4:])[:600]
        except Exception:
            summary = (last_text or "")[:250]

    try:
        _apply_operational_state(
            wa_id,
            workspace_id=workspace_id,
            status="handoff_active",
            step="handoff_waiting",
            waiting_for="human",
            user_patch={
                "stage": "Negociação",
                "lead_stage": "em_negociacao",
                "priority": 3,
                "assigned_to": DEFAULT_ASSIGNEE,
                "handoff_active": True,
                "handoff_at": _now_iso(),
                "attendance_mode": "human",
                "automation_paused": True,
                "bot_enabled": False,
                "human_owner": DEFAULT_ASSIGNEE,
                "notes": (
                    f"ORIGEM DO ENCAMINHAMENTO: {reason_label}\n"
                    f"NOME: {lead_name}\n"
                    f"FRENTE: {topic}\n"
                    "BRIEFING:\n"
                    f"{summary[:900]}"
                ),
            },
            flow_patch={
                "topic": topic,
                "briefing": summary[:1200],
                "context_summary": summary[:900],
                "handoff_reason": reason,
                "handoff_started_at": _now_iso(),
            },
            event="handoff_start",
        )
    except Exception as e:
        print(f"[{cid}] Falha ao atualizar lead no handoff:", repr(e))

    try:
        create_task(
            wa_id,
            f"Assumir atendimento: {topic}",
            datetime.now(timezone.utc).isoformat(),
            workspace_id=workspace_id,
        )
    except Exception as e:
        print(f"[{cid}] Falha ao criar task automática:", repr(e))

    link = _build_handoff_link(topic=topic, wa_id=wa_id, summary=summary, user=user)

    internal_briefing = internal_briefing or (
        f"Olá Julia! Meu nome é {lead_name} e estou interessado em {topic}.\n\n"
        f"ID: {wa_id}\n"
        f"Frente: {topic}\n"
        f"Status: {reason_label}\n\n"
        "Briefing:\n"
        f"{summary}"
    )

    internal_ok_julia = safe_send(
        HUMAN_NUMBER,
        internal_briefing,
        meta={
            "event": "internal_handoff_to_julia",
            "cid": cid,
            "lead_wa_id": wa_id,
            "lead_name": lead_name,
            "topic": topic,
        },
        workspace_id=workspace_id,
        cid=cid,
    )

    internal_ok_eduarda = safe_send(
        EDUARDA_NUMBER,
        internal_briefing,
        meta={
            "event": "internal_handoff_to_eduarda",
            "cid": cid,
            "lead_wa_id": wa_id,
            "lead_name": lead_name,
            "topic": topic,
        },
        workspace_id=workspace_id,
        cid=cid,
    )

    safe_send(
        wa_id,
        (
            "Perfeito. Encaminhei seu atendimento para o time da Mugô.\n\n"
            f"Se quiser adiantar agora, fale direto por aqui:\n{link}"
        ),
        meta={
            "event": "handoff_link",
            "cid": cid,
            "internal_briefing_sent_julia": internal_ok_julia,
            "internal_briefing_sent_eduarda": internal_ok_eduarda,
        },
        workspace_id=workspace_id,
        cid=cid,
    )

    merge_flow_data(
        wa_id,
        {
            "topic": topic,
            "briefing": summary[:1200],
            "current_step": "handoff_waiting",
            "flow_step": "handoff_waiting",
            "last_bot_step": "handoff_link",
            "last_bot_text": (
                "Perfeito. Encaminhei seu atendimento para o time da Mugô.\n\n"
                f"Se quiser adiantar agora, fale direto por aqui:\n{link}"
            )[:900],
            "bot_status": "handoff_active",
            "bot_paused": True,
            "handoff_sent_at": _now_iso(),
            "waiting_after_handoff": True,
            "resume_mode": "",
            "context_summary": summary[:900],
            "handoff_reason": reason,
            "handoff_started_at": _now_iso(),
        },
        workspace_id=workspace_id,
    )


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    cid = uuid.uuid4().hex[:10]
    try:
        data = await request.json()
    except Exception as exc:
        if DEBUG_WEBHOOK:
            print(f"[{cid}] INVALID PAYLOAD:", repr(exc))
        return {"ok": True}

    entry = (data.get("entry") or [])
    if not entry:
        return {"ok": True}

    changes = (entry[0].get("changes") or [])
    if not changes:
        return {"ok": True}

    value = (changes[0].get("value") or {})
    statuses = value.get("statuses") or []
    if statuses:
        return {"ok": True}

    messages = value.get("messages") or []
    if not messages:
        return {"ok": True}

    background_tasks.add_task(_process_webhook_payload, data, cid)
    return {"ok": True}


async def _process_webhook_payload(data: dict, cid: str):
    if DEBUG_WEBHOOK:
        print(f"[{cid}] INCOMING RAW:", _j(data)[:3000])

    try:
        entry = (data.get("entry") or [])
        if not entry:
            return

        changes = (entry[0].get("changes") or [])
        if not changes:
            return

        value = (changes[0].get("value") or {})
        statuses = value.get("statuses") or []
        if statuses:
            return

        messages = value.get("messages") or []
        if not messages:
            return

        workspace_id = resolve_workspace_id()
        msg = messages[0] or {}
        contacts = value.get("contacts", [{}]) or [{}]
        inbound_wa_id_raw, wa_id = _extract_inbound_wa_id(msg, contacts)
        print(f"INBOUND_WA_ID_RAW: {inbound_wa_id_raw}")
        print(f"INBOUND_WA_ID_NORMALIZED: {wa_id}")
        if not wa_id:
            return

        message_id = (msg.get("id") or "").strip()

        if await _dedupe_incoming(wa_id, message_id, cid):
            _log_outbound_skipped(cid, wa_id, "duplicate_inbound_message")
            return

        profile = (contacts[0].get("profile") or {}) if contacts else {}
        name = (profile.get("name") or "").strip()
        telefone = normalize_wa_id((contacts[0].get("wa_id") or wa_id).strip())

        msg_type = (msg.get("type") or "").strip()
        user_text = ""
        choice_id = ""

        if msg_type == "text":
            user_text = ((msg.get("text") or {}).get("body") or "").strip()
        elif msg_type == "interactive":
            inter = msg.get("interactive") or {}
            br = (inter.get("button_reply") or {})
            lr = (inter.get("list_reply") or {})
            choice_id = (br.get("id") or lr.get("id") or "").strip()
            user_text = (br.get("title") or lr.get("title") or "").strip()
        else:
            print(f"[{cid}] WEBHOOK:unsupported_message_type wa_id={wa_id} msg_type={msg_type}")
            print(
                "WEBHOOK_MESSAGE_RECEIVED "
                f"cid={cid} wa_id={wa_id} message_type={msg_type} body='' button_id=''"
            )
            _log_outbound_skipped(cid, wa_id, f"unsupported_message_type:{msg_type}")
            return

        if not user_text and choice_id:
            user_text = choice_id

        if not user_text:
            print(f"[{cid}] WEBHOOK:empty_user_text wa_id={wa_id} msg_type={msg_type} choice_id={choice_id or '-'}")
            print(
                "WEBHOOK_MESSAGE_RECEIVED "
                f"cid={cid} wa_id={wa_id} message_type={msg_type} body='' button_id={choice_id or ''!r}"
            )
            _log_outbound_skipped(cid, wa_id, "empty_user_text")
            return

        print(
            "WEBHOOK_MESSAGE_RECEIVED "
            f"cid={cid} wa_id={wa_id} message_type={msg_type} body={user_text[:240]!r} button_id={choice_id or ''!r}"
        )
        print(
            f"[{cid}] WEBHOOK:message wa_id={wa_id} msg_type={msg_type} "
            f"choice_id={choice_id or '-'} text={user_text[:240]!r}"
        )

        tracking = _extract_source_campaign_from_message(msg, user_text)
        entry_type = _infer_entry_type(tracking.get("source"), tracking.get("campaign"), msg_type)
        attendance_mode = _infer_attendance_mode(tracking.get("source"), tracking.get("campaign"))

        user = upsert_user(
            wa_id,
            name=name,
            telefone=telefone,
            workspace_id=workspace_id,
            assigned_to=DEFAULT_ASSIGNEE,
            stage="Novo",
            lead_stage="novo",
            source=tracking.get("source") or None,
            last_source=tracking.get("source") or None,
            campaign=tracking.get("campaign") or None,
            entry_type=entry_type,
            inbound_type=entry_type,
            attendance_mode=attendance_mode,
        )

        resolved_name = _display_name(user, name, telefone, wa_id)
        lower = user_text.lower().strip()

        log_message(
            wa_id,
            "in",
            user_text,
            meta={
                "src": "whatsapp",
                "type": msg_type,
                "cid": cid,
                "choice_id": choice_id,
                "message_id": message_id,
                "source": tracking.get("source"),
                "campaign": tracking.get("campaign"),
                "entry_type": entry_type,
                "attendance_mode": attendance_mode,
            },
            workspace_id=workspace_id,
        )
        print(f"[{cid}] WEBHOOK:supabase_message_saved wa_id={wa_id} direction=in text_len={len(user_text)}")
        print(f"INBOUND_WA_ID_SAVED: {wa_id}")
        _apply_operational_state(
            wa_id,
            workspace_id=workspace_id,
            flow_patch={
                "last_user_text": _trim_text(user_text),
                "last_user_at": _now_iso(),
                "attendance_mode": current_attendance_mode if 'current_attendance_mode' in locals() else attendance_mode,
            },
            event="state_change",
        )

        ai_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        flow_data = _flow_data(wa_id, workspace_id=workspace_id)
        post_handoff_mode = _is_post_handoff_mode(ai_state)
        automation_paused = bool((user or {}).get("automation_paused"))
        bot_enabled = bool((user or {}).get("bot_enabled", True))
        current_attendance_mode = ((user or {}).get("attendance_mode") or attendance_mode or "").strip().lower()
        handoff_active = bool((user or {}).get("handoff_active") or (user or {}).get("handoff_pending"))
        resume_ready = _is_resume_ready(flow_data, user)

        if _is_back_trigger(lower):
            if post_handoff_mode:
                _log_outbound_decision(cid, wa_id, "fallback", "Já encaminhei seu briefing para o time da Mugô.")
                safe_send(
                    wa_id,
                    "Já encaminhei seu briefing para o time da Mugô. Se quiser, me manda sua dúvida por aqui que eu te ajudo e, se necessário, encaminho novamente. ✅",
                    meta={"event": "post_handoff_back_to_ai", "cid": cid},
                    workspace_id=workspace_id,
                    cid=cid,
                )
                return

            clear_handoff(wa_id, workspace_id=workspace_id)
            try:
                set_handoff_pending(wa_id, False, workspace_id=workspace_id)
            except Exception:
                pass

            await reset_ai_state(wa_id, workspace_id=workspace_id)
            try:
                clear_flow(wa_id, workspace_id=workspace_id)
            except Exception:
                pass

            flow_resp = handle_mugo_flow(wa_id, "start", choice_id="", workspace_id=workspace_id)
            if flow_resp:
                _log_outbound_decision(cid, wa_id, "menu", flow_resp)
                ok = safe_send(wa_id, flow_resp, meta={"event": "back_to_flow_start", "cid": cid}, workspace_id=workspace_id, cid=cid)
                if ok:
                    _remember_bot_message(
                        wa_id,
                        (flow_resp.get("step_key") or "").strip(),
                        _extract_log_text(flow_resp),
                        workspace_id=workspace_id,
                    )
                else:
                    _log_outbound_skipped(cid, wa_id, "send_failed:back_to_flow_start")
                return

            _log_outbound_decision(cid, wa_id, "fallback", _menu_fallback_text())
            safe_send(wa_id, _menu_fallback_text(), meta={"event": "back_to_menu_fallback", "cid": cid}, workspace_id=workspace_id, cid=cid)
            return

        if (choice_id or user_text) in ("BRIEF_RESTART", "brief_restart"):
            try:
                clear_flow(wa_id, workspace_id=workspace_id)
            except Exception:
                pass

            flow_resp = handle_mugo_flow(wa_id, "start", choice_id="", workspace_id=workspace_id)
            if flow_resp:
                _log_outbound_decision(cid, wa_id, "menu", flow_resp)
                ok = safe_send(wa_id, flow_resp, meta={"event": "brief_restart", "cid": cid}, workspace_id=workspace_id, cid=cid)
                if ok:
                    _remember_bot_message(
                        wa_id,
                        (flow_resp.get("step_key") or "").strip(),
                        _extract_log_text(flow_resp),
                        workspace_id=workspace_id,
                    )
                else:
                    _log_outbound_skipped(cid, wa_id, "send_failed:brief_restart")
                return

            _log_outbound_decision(cid, wa_id, "fallback", _menu_fallback_text())
            safe_send(wa_id, _menu_fallback_text(), meta={"event": "brief_restart_fallback", "cid": cid}, workspace_id=workspace_id, cid=cid)
            return

        if (choice_id or user_text) in ("TALK_HUMAN", "talk_human"):
            st = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
            topic = (st.get("handoff_topic") or "Atendimento Mugô").strip()[:100]
            summary = (st.get("handoff_summary") or "").strip()

            if not summary:
                try:
                    hist = get_recent_messages(wa_id, limit=10, workspace_id=workspace_id) or []
                    entradas = [(m.get("text") or "").strip() for m in hist if m.get("direction") == "in"]
                    summary = " | ".join(entradas[-4:])[:600]
                except Exception:
                    summary = ""
            resolved_summary = summary or user_text
            _log_outbound_decision(cid, wa_id, "handoff", resolved_summary)
            start_handoff_now(
                wa_id=wa_id,
                cid=cid,
                reason="ai_handoff",
                topic=topic,
                summary=resolved_summary,
                last_text=user_text,
                user=user,
                workspace_id=workspace_id,
            )
            await mark_handoff_done(wa_id, topic=topic, summary=resolved_summary, workspace_id=workspace_id)
            return

        if handoff_active:
            print(f"[{cid}] WEBHOOK:handoff_active_skip_bot wa_id={wa_id}")
            _log_outbound_skipped(cid, wa_id, "handoff_active")
            _apply_operational_state(
                wa_id,
                workspace_id=workspace_id,
                status="human_active",
                step=(flow_data.get("current_step") or "handoff_waiting"),
                waiting_for="human",
                flow_patch={"last_user_text": _trim_text(user_text), "last_user_at": _now_iso()},
                event="state_change",
            )
            return

        if post_handoff_mode and resume_ready:
            resume_text = _build_resume_message(flow_data, ai_state)
            if _should_skip_duplicate_bot_message(wa_id, "resume_after_handoff", resume_text, workspace_id=workspace_id):
                _log_outbound_skipped(cid, wa_id, "duplicate_resume_after_handoff")
                _apply_operational_state(
                    wa_id,
                    workspace_id=workspace_id,
                    status="ai_active",
                    step="ai_resume",
                    waiting_for="customer",
                    flow_patch={
                        "resume_mode": "resumed_after_handoff",
                        "bot_paused": False,
                        "waiting_after_handoff": False,
                        "resumed_at": _now_iso(),
                    },
                    event="resume",
                )
                return

            _log_outbound_decision(cid, wa_id, "ai", resume_text)
            ok = safe_send(
                wa_id,
                resume_text,
                meta={"event": "resume_after_handoff", "cid": cid},
                workspace_id=workspace_id,
                cid=cid,
            )
            if ok:
                _remember_bot_message(wa_id, "resume_after_handoff", resume_text, workspace_id=workspace_id)
                _apply_operational_state(
                    wa_id,
                    workspace_id=workspace_id,
                    status="ai_active",
                    step="ai_resume",
                    waiting_for="customer",
                    flow_patch={
                        "resume_mode": "resumed_after_handoff",
                        "bot_paused": False,
                        "waiting_after_handoff": False,
                        "resumed_at": _now_iso(),
                    },
                    event="resume",
                )
            return

        if automation_paused or not bot_enabled or current_attendance_mode == "human":
            print(
                f"[{cid}] WEBHOOK:automation_paused wa_id={wa_id} "
                f"automation_paused={automation_paused} bot_enabled={bot_enabled} attendance_mode={current_attendance_mode}"
            )
            _log_outbound_skipped(cid, wa_id, "automation_paused_or_human_mode")
            _apply_operational_state(
                wa_id,
                workspace_id=workspace_id,
                status="paused",
                step=(flow_data.get("current_step") or ""),
                waiting_for="human",
                flow_patch={"last_user_text": _trim_text(user_text), "last_user_at": _now_iso()},
                event="state_change",
            )
            return

        flow_resp = None
        service_context = {}

        selected_choice = choice_id or (user_text if is_service_choice(user_text) else "")
        if selected_choice and is_service_choice(selected_choice):
            print(f"[{cid}] WEBHOOK:service_choice_to_ai wa_id={wa_id} choice_id={selected_choice}")
            service_context = apply_service_choice(wa_id, selected_choice, workspace_id=workspace_id)
            try:
                mark_first_message_sent(wa_id, workspace_id=workspace_id)
            except Exception:
                pass
            ai_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
            brain_updates = sales_brain.service_choice_update(selected_choice)
            brain_state = sales_brain.merge_state(ai_state, brain_updates)
            await upsert_ai_state(
                wa_id,
                {
                    **brain_state,
                    "selected_service_id": service_context.get("id"),
                    "selected_service": service_context.get("service_interest"),
                    "service_interest": service_context.get("service_interest"),
                    "intent": service_context.get("intent") or brain_state.get("intent") or "",
                    "lead_fields": _merge_lead_fields(
                        brain_state.get("lead_fields"),
                        {
                            "service_interest": service_context.get("service_interest"),
                            "intent": service_context.get("intent"),
                            "funnel_stage": "qualificacao",
                            "last_question_asked": brain_updates.get("last_question_asked"),
                            "last_question_category": brain_updates.get("last_question_category"),
                            "next_best_question": brain_updates.get("next_best_question"),
                        },
                    ),
                },
                workspace_id=workspace_id,
            )
            user_text = service_context.get("label") or user_text
            lower = user_text.lower().strip()
        elif choice_id and not post_handoff_mode:
            print(f"[{cid}] WEBHOOK:enter_mugo_flow wa_id={wa_id} choice_id={choice_id}")
            flow_resp = handle_mugo_flow(wa_id, choice_id, choice_id=choice_id, workspace_id=workspace_id)

        if flow_resp:
            ftype = (flow_resp.get("type") or "").lower().strip()
            print(f"[{cid}] WEBHOOK:mugo_flow_response wa_id={wa_id} type={ftype} step={flow_resp.get('step_key') or '-'}")

            if ftype == "ai_context":
                service_context = flow_resp.get("service_context") or {}

            if ftype in ("buttons", "text", "list"):
                step_key = (flow_resp.get("step_key") or "").strip()
                bot_text = _extract_log_text(flow_resp)

                if _should_skip_duplicate_bot_message(wa_id, step_key, bot_text, workspace_id=workspace_id):
                    print(f"[{cid}] DUPLICATE FLOW MESSAGE SKIPPED -> {wa_id} / {step_key}")
                    _log_outbound_skipped(cid, wa_id, f"duplicate_flow_message:{step_key}")
                    return

                if not bool(user.get("first_message_sent")):
                    try:
                        mark_first_message_sent(wa_id, workspace_id=workspace_id)
                    except Exception:
                        pass

                _log_outbound_decision(cid, wa_id, "menu" if ftype in {"buttons", "list"} else "fallback", flow_resp)
                ok = safe_send(
                    wa_id,
                    flow_resp,
                    meta={"src": "mugo_flow", "cid": cid, "choice_id": choice_id, "message_id": message_id},
                    workspace_id=workspace_id,
                    cid=cid,
                )
                if not ok and ftype in ("buttons", "list"):
                    print(f"[{cid}] WEBHOOK:mugo_flow_interactive_failed_manual_fallback wa_id={wa_id} type={ftype}")
                    _log_outbound_decision(cid, wa_id, "fallback", _menu_fallback_text())
                    safe_send(wa_id, _menu_fallback_text(), meta={"event": "flow_menu_fallback", "cid": cid}, workspace_id=workspace_id, cid=cid)
                if ok:
                    _remember_bot_message(wa_id, step_key, bot_text, workspace_id=workspace_id)
                    _apply_operational_state(
                        wa_id,
                        workspace_id=workspace_id,
                        status="bot_active",
                        step=step_key,
                        waiting_for="customer",
                        flow_patch={"last_bot_text": _trim_text(bot_text), "last_bot_at": _now_iso()},
                        event="state_change",
                    )
                else:
                    _log_outbound_skipped(cid, wa_id, f"send_failed:mugo_flow:{ftype}")
                return

            if ftype == "handoff":
                print(f"[{cid}] WEBHOOK:mugo_flow_handoff wa_id={wa_id}")
                topic = (flow_resp.get("topic") or "").strip() or "Atendimento Mugô"
                summary = (flow_resp.get("summary") or "").strip()
                _log_outbound_decision(cid, wa_id, "handoff", summary)

                start_handoff_now(
                    wa_id=wa_id,
                    cid=cid,
                    reason="flow_completed",
                    topic=topic,
                    summary=summary,
                    last_text=user_text,
                    user=user,
                    workspace_id=workspace_id,
                )

                await mark_handoff_done(wa_id, topic=topic, summary=summary, workspace_id=workspace_id)
                return

        if msg_type == "interactive" and choice_id and not post_handoff_mode and not service_context:
            flow_resp2 = handle_mugo_flow(wa_id, "start", choice_id="", workspace_id=workspace_id)
            if flow_resp2:
                _log_outbound_decision(cid, wa_id, "menu", flow_resp2)
                ok = safe_send(wa_id, flow_resp2, meta={"event": "interactive_flow_recover", "cid": cid}, workspace_id=workspace_id, cid=cid)
                if ok:
                    _remember_bot_message(
                        wa_id,
                        (flow_resp2.get("step_key") or "").strip(),
                        _extract_log_text(flow_resp2),
                        workspace_id=workspace_id,
                    )
                    _apply_operational_state(
                        wa_id,
                        workspace_id=workspace_id,
                        status="bot_active",
                        step=(flow_resp2.get("step_key") or "").strip(),
                        waiting_for="customer",
                        event="state_change",
                    )
                else:
                    _log_outbound_skipped(cid, wa_id, "send_failed:interactive_flow_recover")
                return
            _log_outbound_decision(cid, wa_id, "fallback", _menu_fallback_text())
            safe_send(wa_id, _menu_fallback_text(), meta={"event": "interactive_fallback_text", "cid": cid}, workspace_id=workspace_id, cid=cid)
            return

        if not bool(user.get("first_message_sent")) and not post_handoff_mode and not choice_id and lower in {"oi", "oie", "olá", "ola", "opa", "start", "menu", "quero saber mais"}:
            print(f"[{cid}] WEBHOOK:first_interaction_menu wa_id={wa_id} text={lower!r}")
            flow_start = handle_mugo_flow(wa_id, "start", choice_id="", workspace_id=workspace_id)
            if flow_start:
                try:
                    mark_first_message_sent(wa_id, workspace_id=workspace_id)
                except Exception:
                    pass
                _log_outbound_decision(cid, wa_id, "menu", flow_start)
                ok = safe_send(wa_id, flow_start, meta={"event": "auto_flow_start", "cid": cid}, workspace_id=workspace_id, cid=cid)
                if ok:
                    _remember_bot_message(
                        wa_id,
                        (flow_start.get("step_key") or "").strip(),
                        _extract_log_text(flow_start),
                        workspace_id=workspace_id,
                    )
                    _apply_operational_state(
                        wa_id,
                        workspace_id=workspace_id,
                        status="bot_active",
                        step=(flow_start.get("step_key") or "").strip(),
                        waiting_for="customer",
                        event="state_change",
                    )
                else:
                    _log_outbound_skipped(cid, wa_id, "send_failed:auto_flow_start")
                return
            _log_outbound_decision(cid, wa_id, "fallback", _menu_fallback_text())
            safe_send(wa_id, _menu_fallback_text(), meta={"event": "auto_flow_start_fallback", "cid": cid}, workspace_id=workspace_id, cid=cid)
            return

        flow_data = _flow_data(wa_id, workspace_id=workspace_id)
        recent_messages = get_recent_messages(wa_id, limit=12, workspace_id=workspace_id) or []
        lead_context = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
        lead_context = await _prepare_sales_brain_state(
            wa_id,
            ai_state=lead_context,
            user_text=user_text,
            workspace_id=workspace_id,
            cid=cid,
        )
        print(
            f"[{cid}] WEBHOOK:enter_ai wa_id={wa_id} text_len={len(user_text)} "
            f"recent_messages={len(recent_messages)} selected_service={lead_context.get('selected_service') or '-'}"
        )

        result = await generate_reply(
            wa_id=wa_id,
            user_message=user_text,
            first_message_sent=True,
            name=resolved_name,
            telefone=telefone,
            recent_messages=recent_messages,
            lead_context=lead_context,
        )
        if service_context:
            result["intent"] = result.get("intent") or service_context.get("intent")
            result["lead_theme"] = result.get("lead_theme") or service_context.get("intent")
            result["lead_fields"] = _merge_lead_fields(
                result.get("lead_fields"),
                {"service_interest": service_context.get("service_interest")},
            )
            if service_context.get("intent") == "humano":
                result["handoff"] = True
                result["next_action"] = "handoff"
                result["handoff_reason"] = result.get("handoff_reason") or "lead_pediu_humano"
                result["lead_temperature"] = "hot"
                result["briefing_ready"] = True

        if _is_human_service_choice(result, user_text):
            result["handoff"] = True
            result["next_action"] = "handoff"
            result["handoff_reason"] = result.get("handoff_reason") or "lead_pediu_humano"
            result["lead_temperature"] = "hot"
            result["briefing_ready"] = True

        result = _postprocess_ai_result(
            cid=cid,
            wa_id=wa_id,
            result=result,
            ai_state=lead_context,
            user_text=user_text,
        )

        if _is_human_service_choice(result, user_text):
            result["handoff"] = True
            result["next_action"] = "handoff"
            result["handoff_reason"] = result.get("handoff_reason") or "lead_pediu_humano"
            result["lead_temperature"] = "hot"
            result["briefing_ready"] = True

        print(
            f"[{cid}] WEBHOOK:ai_result wa_id={wa_id} "
            f"intent={result.get('intent')} next_action={result.get('next_action')} "
            f"lead_temperature={result.get('lead_temperature')} handoff={result.get('handoff')} "
            f"meeting_suggested={result.get('meeting_suggested')} briefing_ready={result.get('briefing_ready')} "
            f"reply_len={len((result.get('reply') or '').strip())}"
        )

        try:
            set_tags(wa_id, _extract_auto_tags(result), workspace_id=workspace_id)
        except Exception:
            pass

        try:
            ai_state = await get_ai_state(wa_id, workspace_id=workspace_id) or {}
            await _save_ai_result_state(
                wa_id,
                ai_state=ai_state,
                result=result,
                user_text=user_text,
                workspace_id=workspace_id,
            )
        except Exception as e:
            print(f"[{cid}] Falha ao salvar memória da IA:", repr(e))

        try:
            upsert_user(
                wa_id,
                workspace_id=workspace_id,
                lead_score=result.get("lead_score") or 0,
                lead_temperature=result.get("lead_temperature") or "frio",
                lead_theme=result.get("lead_theme") or "indefinido",
            )
        except Exception:
            pass

        reply_text = (result.get("reply") or "").strip() or "Em uma frase: qual é o foco agora?"

        print(f"[{cid}] WEBHOOK:send_ai_reply wa_id={wa_id} reply_len={len(reply_text)}")
        _log_outbound_decision(cid, wa_id, "ai", reply_text)
        ai_sent = safe_send(wa_id, reply_text, meta={"src": "ai", "cid": cid, "message_id": message_id}, workspace_id=workspace_id, cid=cid)
        if ai_sent:
            _remember_bot_message(wa_id, "ai_reply", reply_text, workspace_id=workspace_id)
            _apply_operational_state(
                wa_id,
                workspace_id=workspace_id,
                status="ai_active",
                step=(flow_data.get("current_step") or "ai_reply"),
                waiting_for="customer",
                flow_patch={
                    "last_ai_text": _trim_text(reply_text),
                    "last_ai_at": _now_iso(),
                    "context_summary": _trim_text(result.get("memory_summary") or flow_data.get("context_summary") or "", 900),
                },
                event="state_change",
            )
        else:
            _log_outbound_skipped(cid, wa_id, "send_failed:ai_reply")

        if _should_trigger_internal_briefing(result):
            print(
                f"[{cid}] WEBHOOK:ai_operational_decision wa_id={wa_id} "
                f"handoff={result.get('handoff')} briefing_ready={result.get('briefing_ready')} next_action={result.get('next_action')}"
            )

        await _handle_ai_operational_decision(
            wa_id=wa_id,
            cid=cid,
            result=result,
            user_text=user_text,
            user=user,
            workspace_id=workspace_id,
        )

    except Exception as e:
        print(f"[{cid}] Erro no webhook:", repr(e))
        if DEBUG_WEBHOOK:
            print(f"[{cid}] PAYLOAD:", _j(data)[:4000])
