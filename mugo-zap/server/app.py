import os
import json
import uuid
import urllib.parse
import asyncio
import traceback
from pathlib import Path
from typing import Any, Optional, List, Dict, Union, Set
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse, JSONResponse

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)

VERIFY_TOKEN = (os.getenv("VERIFY_TOKEN") or "mugo_verify").strip()
ALLOW_ORIGIN = (os.getenv("ALLOW_ORIGIN") or "").strip()
PANEL_API_KEY = (os.getenv("PANEL_API_KEY") or "").strip()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_API_KEY = SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY

HUMAN_NUMBER = (os.getenv("HUMAN_NUMBER") or "5511973510549").strip()
DEBUG_WEBHOOK = (os.getenv("DEBUG_WEBHOOK") or "").strip().lower() in ("1", "true", "yes")

from services.ai_state import get_ai_state, upsert_ai_state, reset_ai_state
from services.state import (
    mark_first_message_sent,
    log_message,
    list_conversations,
    get_recent_messages,
    set_handoff_pending,
    set_handoff_topic,
    clear_handoff,
    upsert_user,
    set_stage,
    set_notes,
    set_tags,
    create_task,
    list_tasks,
    done_task,
    update_task,
    update_lead_intelligence,
)
from services.whatsapp import send_message
from services.openai_client import generate_reply
from services.mugo_flow import handle_mugo_flow

app = FastAPI()

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("\n=== UNHANDLED SERVER ERROR ===")
    print("PATH:", request.url.path)
    print("ERROR:", repr(exc))
    traceback.print_exc()
    print("=== /UNHANDLED SERVER ERROR ===\n")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# CORS
ALLOW_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
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

def _j(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)

def _lead_signal_bump(lower_text: str) -> int:
    t = (lower_text or "").lower()
    bump = 0
    if any(k in t for k in ["orçamento", "orcamento", "preço", "preco", "valor", "valores", "quanto custa", "proposta"]):
        bump += 35
    if any(k in t for k in ["prazo", "cronograma", "quando fica pronto", "essa semana", "urgente", "hoje", "amanhã"]):
        bump += 20
    if any(k in t for k in ["fechar", "contrato", "assinar", "começar", "comecar"]):
        bump += 25
    return min(100, bump)

def safe_send(
    to_wa_id: str,
    payload: Union[str, Dict[str, Any]],
    *,
    meta: Optional[dict] = None,
    cid: str = ""
) -> bool:
    if not to_wa_id:
        return False

    if isinstance(payload, str):
        log_text = (payload or "").strip()
        if not log_text:
            return False
    elif isinstance(payload, dict):
        log_text = (payload.get("text") or "").strip()
        if not log_text:
            log_text = "[interactive]"
    else:
        return False

    try:
        send_message(to_wa_id, payload)
        try:
            log_message(to_wa_id, "out", log_text, meta=meta or {})
        except Exception as e:
            print(f"[{cid}] log_message(out) failed:", repr(e))
        if DEBUG_WEBHOOK:
            print(f"[{cid}] SEND OK -> {to_wa_id}: {log_text[:140]}")
        return True
    except Exception as e:
        print(f"[{cid}] SEND FAIL -> {to_wa_id}:", repr(e))
        try:
            log_message(to_wa_id, "out", f"[ERRO ENVIO] {e}", meta={"event": "send_fail", "cid": cid})
        except Exception:
            pass
        return False

def start_handoff_now(
    *,
    wa_id: str,
    cid: str,
    reason: str,
    topic: str = "",
    summary: str = "",
    last_text: str = "",
):
    topic = (topic or reason or "Atendimento").strip()[:100]

    try:
        set_handoff_pending(wa_id, False)
        set_handoff_topic(wa_id, topic)
    except Exception as e:
        print(f"[{cid}] Falha ao atualizar handoff:", repr(e))

    if not summary:
        try:
            hist = get_recent_messages(wa_id, limit=6) or []
            entradas = [(m.get("text") or "").strip() for m in hist if m.get("direction") == "in"]
            summary = " | ".join(entradas[-3:])[:200]
        except Exception:
            summary = (last_text or "")[:150]

    try:
        notes = f"MOTIVO: {reason}\nTEMA: {topic}\nCONTEXTO: {summary}"
        set_notes(wa_id, notes)
    except Exception:
        pass

    link_text = f"Olá! Preciso de atendimento estratégico.\n\nAssunto: {topic}\nID: {wa_id}"
    encoded_text = urllib.parse.quote(link_text)
    link = f"https://wa.me/{HUMAN_NUMBER}?text={encoded_text}"

    safe_send(
        wa_id,
        "Perfeito. Vou direcionar você agora para um especialista dar sequência.",
        meta={"event": "handoff_now", "cid": cid},
        cid=cid,
    )
    safe_send(
        wa_id,
        f"Toque no link para iniciar:\n{link}",
        meta={"event": "handoff_link", "cid": cid},
        cid=cid,
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_webhook(request: Request):
    cid = uuid.uuid4().hex[:10]
    data = await request.json()

    if DEBUG_WEBHOOK:
        print(f"[{cid}] INCOMING RAW:", _j(data)[:3000])

    wa_id: Optional[str] = None
    msg_type: Optional[str] = None
    user_text: Optional[str] = None
    choice_id: str = ""
    flow_context: Dict[str, Any] = {}

    try:
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

        msg = messages[0] or {}
        wa_id = (msg.get("from") or "").strip()
        if not wa_id:
            return {"ok": True}

        contacts = value.get("contacts", [{}]) or [{}]
        profile = (contacts[0].get("profile") or {}) if contacts else {}
        name = (profile.get("name") or "").strip()
        telefone = (contacts[0].get("wa_id") or wa_id).strip()

        user = upsert_user(wa_id, name=name, telefone=telefone)
        ai_state = await get_ai_state(wa_id)

        msg_type = (msg.get("type") or "").strip()

        if msg_type == "text":
            user_text = ((msg.get("text") or {}).get("body") or "").strip()

        elif msg_type == "interactive":
            inter = msg.get("interactive") or {}
            br = (inter.get("button_reply") or {})
            lr = (inter.get("list_reply") or {})
            choice_id = (br.get("id") or lr.get("id") or "").strip()
            user_text = (br.get("title") or lr.get("title") or "").strip()

        else:
            return {"ok": True}

        if not user_text:
            return {"ok": True}

        lower = user_text.lower().strip()

        # LOG IN
        log_message(wa_id, "in", user_text, meta={"src": "whatsapp", "type": msg_type, "cid": cid, "choice_id": choice_id})

        # 1) SE handoff ativo
        if bool(user.get("handoff_active")):
            safe_send(
                wa_id,
                'Seu atendimento já foi direcionado. Para retornar ao bot, digite "voltar".',
                meta={"event": "handoff_active_block", "cid": cid},
                cid=cid,
            )
            return {"ok": True}

        # 2) FLOW SEMPRE PRIMEIRO (E SE DER ERRO, MANDA MENU)
        try:
            flow_resp = handle_mugo_flow(wa_id, user_text, choice_id=choice_id)
        except Exception as e:
            print(f"[{cid}] mugo_flow failed:", repr(e))
            flow_resp = {"type": "buttons", "text": "Qual é o foco agora?", "buttons": [
                {"id": "FLOW_AUTOMATIZAR", "title": "⚙️ Automação"},
                {"id": "FLOW_SITE", "title": "🌐 Site / Loja"},
                {"id": "FLOW_SOCIAL", "title": "📈 Social/Tráfego"},
            ]}

        if flow_resp:
            ftype = (flow_resp.get("type") or "").lower()

            # flow devolvendo botões/texto normal
            if ftype in ("buttons", "text"):
                safe_send(wa_id, flow_resp, meta={"src": "mugo_flow", "cid": cid}, cid=cid)
                return {"ok": True}

            # flow finalizou -> IA entra -> SEMPRE HANDOFF
            if ftype == "ai":
                flow_context = flow_resp.get("flow_context") or {}
                ai_user_msg = (flow_resp.get("user_message") or user_text or "").strip()

                result = generate_reply(
                    wa_id=wa_id,
                    user_message=ai_user_msg,
                    first_message_sent=True,
                    name=name,
                    telefone=telefone,
                    flow_context=flow_context,
                )

                reply_text = (result.get("reply") or "").strip() or "Perfeito. Vou te encaminhar agora."
                handoff_summary = (result.get("handoff_summary") or "").strip() or ai_user_msg[:220]

                safe_send(wa_id, reply_text, meta={"src": "ai_after_flow", "cid": cid}, cid=cid)

                # ✅ REGRA: SEMPRE handoff após IA (pós-flow)
                start_handoff_now(
                    wa_id=wa_id,
                    cid=cid,
                    reason="flow_completed",
                    topic="Lead qualificado (botões)",
                    summary=handoff_summary,
                    last_text=user_text,
                )
                return {"ok": True}

        # 3) SE por algum motivo flow não respondeu -> manda menu (pra nunca cair direto em IA no primeiro contato)
        if not bool(user.get("first_message_sent")):
            safe_send(
                wa_id,
                {
                    "type": "buttons",
                    "text": "Oi! O que você quer destravar agora?",
                    "buttons": [
                        {"id": "FLOW_AUTOMATIZAR", "title": "⚙️ Automação"},
                        {"id": "FLOW_SITE", "title": "🌐 Site / Loja"},
                        {"id": "FLOW_SOCIAL", "title": "📈 Social/Tráfego"},
                    ],
                },
                meta={"event": "intro_buttons_fallback", "cid": cid},
                cid=cid,
            )
            mark_first_message_sent(wa_id)
            return {"ok": True}

        # 4) IA normal (fora do flow) — responde e, se qualificar, faz handoff
        result = generate_reply(
            wa_id=wa_id,
            user_message=user_text,
            first_message_sent=True,
            name=name,
            telefone=telefone,
            flow_context=flow_context if flow_context else None,
        )

        reply_text = (result.get("reply") or "").strip() or "Em 1 frase: qual é o foco agora?"
        safe_send(wa_id, reply_text, meta={"src": "ai", "cid": cid}, cid=cid)

        if bool(result.get("handoff")):
            start_handoff_now(
                wa_id=wa_id,
                cid=cid,
                reason=str(result.get("next_intent") or "ai_handoff"),
                topic="Encaminhado pela IA",
                summary=(result.get("handoff_summary") or user_text)[:220],
                last_text=user_text,
            )

        return {"ok": True}

    except Exception as e:
        print(f"[{cid}] Erro no webhook:", repr(e))
        if DEBUG_WEBHOOK:
            print(f"[{cid}] PAYLOAD:", _j(data)[:4000])
        return {"ok": True}