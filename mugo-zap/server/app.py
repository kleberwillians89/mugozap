# mugo-zap/server/app.py
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


# ============================================================
# ENV
# ============================================================
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
DEBUG_WEBHOOK = (os.getenv("DEBUG_WEBHOOK") or "").strip().lower() in ("1", "true")


# ============================================================
# IMPORTS
# ============================================================
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


# ============================================================
# APP
# ============================================================
app = FastAPI()


# ============================================================
# ERROR HANDLER
# ============================================================
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("\n=== UNHANDLED SERVER ERROR ===")
    print("PATH:", request.url.path)
    traceback.print_exc()
    print("=== /UNHANDLED SERVER ERROR ===\n")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# ============================================================
# CORS
# ============================================================
ALLOW_ORIGINS = [
    "http://localhost:5173",
    "https://mugo-zap-web.onrender.com",
]
if ALLOW_ORIGIN:
    ALLOW_ORIGINS.append(ALLOW_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(ALLOW_ORIGINS)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPERS
# ============================================================
def safe_send(
    to_wa_id: str,
    payload: Union[str, Dict[str, Any]],
    *,
    meta: Optional[dict] = None,
    cid: str = ""
):
    try:
        send_message(to_wa_id, payload)
        text_log = payload if isinstance(payload, str) else payload.get("text", "")
        log_message(to_wa_id, "out", text_log, meta=meta or {})
        return True
    except Exception as e:
        print(f"[{cid}] SEND FAIL:", e)
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
    topic = topic or reason or "Atendimento"

    set_handoff_pending(wa_id, False)
    set_handoff_topic(wa_id, topic)

    link_text = f"Olá! Preciso de atendimento.\nAssunto: {topic}\nID: {wa_id}"
    encoded = urllib.parse.quote(link_text)
    link = f"https://wa.me/{HUMAN_NUMBER}?text={encoded}"

    safe_send(wa_id, "Perfeito. Vou te encaminhar agora para um especialista.")
    safe_send(wa_id, f"Toque no link para continuar:\n{link}")


# ============================================================
# HEALTH
# ============================================================
@app.get("/health")
def health():
    return {"ok": True}


# ============================================================
# WEBHOOK VERIFY
# ============================================================
@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403)


# ============================================================
# WEBHOOK MAIN
# ============================================================
@app.post("/webhook")
async def receive_webhook(request: Request):

    cid = uuid.uuid4().hex[:8]

    try:
        data = await request.json()

        entry = (data.get("entry") or [])
        if not entry:
            return {"ok": True}

        changes = (entry[0].get("changes") or [])
        if not changes:
            return {"ok": True}

        value = (changes[0].get("value") or {})
        messages = value.get("messages") or []
        if not messages:
            return {"ok": True}

        msg = messages[0]
        wa_id = (msg.get("from") or "").strip()
        if not wa_id:
            return {"ok": True}

        contacts = value.get("contacts", [{}])
        profile = (contacts[0].get("profile") or {})
        name = profile.get("name", "")
        telefone = contacts[0].get("wa_id", wa_id)

        user = upsert_user(wa_id, name=name, telefone=telefone)
        ai_state = await get_ai_state(wa_id)

        # ========= extrai texto =========
        msg_type = msg.get("type")
        user_text = ""
        choice_id = ""

        if msg_type == "text":
            user_text = msg["text"]["body"]

        elif msg_type == "interactive":
            inter = msg["interactive"]
            choice_id = (
                inter.get("button_reply", {}).get("id")
                or inter.get("list_reply", {}).get("id")
                or ""
            )
            user_text = (
                inter.get("button_reply", {}).get("title")
                or inter.get("list_reply", {}).get("title")
                or ""
            )

        if not user_text:
            return {"ok": True}

        log_message(wa_id, "in", user_text)

        # ==================================================
        # FLOW PRIMEIRO
        # ==================================================
        flow_resp = handle_mugo_flow(wa_id, user_text, choice_id=choice_id)

        if flow_resp:

            # resposta normal do fluxo
            if flow_resp.get("type") in ("buttons", "text"):
                safe_send(wa_id, flow_resp)
                return {"ok": True}

            # final do flow -> IA + Handoff
            if flow_resp.get("type") == "ai":
                flow_context = flow_resp.get("flow_context") or {}
                ai_user_msg = flow_resp.get("user_message") or user_text

                result = generate_reply(
                    wa_id=wa_id,
                    user_message=ai_user_msg,
                    first_message_sent=True,
                    name=name,
                    telefone=telefone,
                    flow_context=flow_context,
                )

                reply = result.get("reply") or "Perfeito. Vou te encaminhar agora."

                safe_send(wa_id, reply)

                start_handoff_now(
                    wa_id=wa_id,
                    cid=cid,
                    reason="flow_completed",
                    topic="Lead qualificado",
                    summary=result.get("handoff_summary") or ai_user_msg,
                    last_text=user_text,
                )

                return {"ok": True}

        # ==================================================
        # IA NORMAL
        # ==================================================
        result = generate_reply(
            wa_id=wa_id,
            user_message=user_text,
            first_message_sent=True,
            name=name,
            telefone=telefone,
        )

        reply = result.get("reply") or "Em uma frase: qual é o foco agora?"
        safe_send(wa_id, reply)

        if result.get("handoff"):
            start_handoff_now(
                wa_id=wa_id,
                cid=cid,
                reason="ai_handoff",
                topic="Encaminhado pela IA",
                summary=result.get("handoff_summary") or user_text,
                last_text=user_text,
            )

        return {"ok": True}

    except Exception as e:
        print(f"[{cid}] ERRO:", e)
        traceback.print_exc()
        return {"ok": True}