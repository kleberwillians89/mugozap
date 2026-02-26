# mugo-zap/server/app.py
import os
import json
import uuid
import urllib.parse
import traceback
import asyncio
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse

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
DEBUG_WEBHOOK = (os.getenv("DEBUG_WEBHOOK") or "").strip().lower() in ("1", "true", "yes")

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
    clear_flow,
    get_flow,
)

from services.whatsapp import send_message
from services.openai_client import generate_reply
from services.mugo_flow import handle_mugo_flow

# ============================================================
# APP
# ============================================================
app = FastAPI()


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

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env (raiz do projeto)")
    if not SUPABASE_API_KEY:
        raise RuntimeError("Missing SUPABASE_ANON_KEY (or SERVICE_ROLE fallback) in .env")


# ============================================================
# CORS
# ============================================================
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

# ============================================================
# Auth (Supabase JWT OR X-Panel-Key)
# ============================================================
async def _supabase_get_user(access_token: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        raise HTTPException(status_code=500, detail="Supabase env not configured")

    access_token = (access_token or "").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing token")

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_API_KEY,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return resp.json()


async def get_current_user(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
) -> dict:
    if PANEL_API_KEY and x_panel_key and x_panel_key == PANEL_API_KEY:
        return {"role": "panel"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    return await _supabase_get_user(token)


# ============================================================
# Helpers
# ============================================================
def _j(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _menu_fallback_text() -> str:
    return (
        "Escolhe uma opção (responda com 1, 2 ou 3):\n"
        "1) Automação\n"
        "2) Site / E-commerce\n"
        "3) Social / Tráfego"
    )


def _is_back_trigger(lower: str) -> bool:
    lower = (lower or "").strip()
    return lower in {"voltar", "volta", "menu", "início", "inicio", "robô", "robo", "bot"}


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
    cid: str = ""
) -> bool:
    if not to_wa_id:
        return False

    log_text = _extract_log_text(payload)
    if not log_text:
        return False

    try:
        send_message(to_wa_id, payload)
        try:
            log_message(to_wa_id, "out", log_text, meta=meta or {})
        except Exception as e:
            print(f"[{cid}] log_message(out) failed:", repr(e))

        if DEBUG_WEBHOOK:
            print(f"[{cid}] SEND OK -> {to_wa_id}: {log_text[:160]}")
        return True

    except Exception as e:
        print(f"[{cid}] SEND FAIL -> {to_wa_id}:", repr(e))
        try:
            if isinstance(payload, dict) and (payload.get("type") or "").lower().strip() in ("buttons", "list"):
                send_message(to_wa_id, _menu_fallback_text())
        except Exception as _e2:
            print(f"[{cid}] FALLBACK SEND FAIL -> {to_wa_id}:", repr(_e2))

        try:
            log_message(to_wa_id, "out", f"[ERRO ENVIO] {e}", meta={"event": "send_fail", "cid": cid})
        except Exception:
            pass
        return False


# ============================================================
# HEALTH
# ============================================================
@app.get("/health")
def health():
    return {"ok": True, "env_path": str(ENV_PATH), "supabase_ok": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)}


# ============================================================
# PANEL API (Front)
# ============================================================
@app.get("/api/conversations")
async def api_conversations(
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
):
    _ = await get_current_user(authorization=authorization, x_panel_key=x_panel_key)
    items = list_conversations(limit=200) or []
    return {"ok": True, "items": items}


@app.get("/api/messages")
async def api_messages(
    wa_id: str = Query(...),
    limit: int = Query(60),
    authorization: str = Header(None),
    x_panel_key: str = Header(None, alias="X-Panel-Key"),
):
    _ = await get_current_user(authorization=authorization, x_panel_key=x_panel_key)
    msgs = get_recent_messages(wa_id, limit=int(limit)) or []
    return {"ok": True, "items": msgs}


# ============================================================
# SSE (EventSource) para painel atualizar
# Front chama: /events?token=...
# ============================================================
@app.get("/events")
async def sse_events(token: str = Query("")):
    token = (token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # valida token supabase (EventSource não manda header)
    _ = await _supabase_get_user(token)

    async def event_gen():
        # handshake
        yield "event: ready\ndata: ok\n\n"

        # loop: envia "conversations" a cada 2s
        while True:
            try:
                items = list_conversations(limit=200) or []
                payload = json.dumps({"type": "conversations", "items": items}, ensure_ascii=False)
                yield f"event: conversations\ndata: {payload}\n\n"
            except Exception as e:
                err = json.dumps({"type": "error", "detail": str(e)}, ensure_ascii=False)
                yield f"event: error\ndata: {err}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# WEBHOOK verify (Meta)
# ============================================================
@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


# ============================================================
# Handoff helpers
# ============================================================
async def mark_handoff_done(wa_id: str, topic: str = "", summary: str = ""):
    try:
        await upsert_ai_state(
            wa_id,
            {
                "handoff_done": True,
                "handoff_done_at": datetime.now(timezone.utc).isoformat(),
                "handoff_topic": (topic or "").strip()[:120],
                "handoff_summary": (summary or "").strip()[:900],
            },
        )
    except Exception:
        pass


def _build_handoff_link(topic: str, wa_id: str, summary: str) -> str:
    topic = (topic or "").strip()
    summary = (summary or "").strip()

    link_text = (
        "Olá Julia! Chegou um lead pelo MugôZap.\n\n"
        f"ID: {wa_id}\n"
        f"Assunto: {topic}\n\n"
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
):
    topic = (topic or reason or "Atendimento").strip()[:100]

    try:
        set_handoff_pending(wa_id, False)
        set_handoff_topic(wa_id, topic)
    except Exception as e:
        print(f"[{cid}] Falha ao atualizar status de handoff: {e}")

    try:
        upsert_user(wa_id, lead_stage="em_negociacao", priority=3)
    except Exception as e:
        print(f"[{cid}] Falha ao setar lead_stage em_negociacao:", repr(e))

    if not summary:
        try:
            hist = get_recent_messages(wa_id, limit=10) or []
            entradas = [(m.get("text") or "").strip() for m in hist if m.get("direction") == "in"]
            summary = " | ".join(entradas[-4:])[:600]
        except Exception:
            summary = (last_text or "")[:250]

    try:
        notes = f"MOTIVO: {reason}\nTEMA: {topic}\nCONTEXTO:\n{summary}"
        set_notes(wa_id, notes)
    except Exception:
        pass

    link = _build_handoff_link(topic=topic, wa_id=wa_id, summary=summary)

    safe_send(
        wa_id,
        "Perfeito. Encaminhei para a Julia dar sequência com você. ✅",
        meta={"event": "handoff_now", "cid": cid},
        cid=cid,
    )
    safe_send(
        wa_id,
        f"Se quiser falar agora, toque no link:\n{link}",
        meta={"event": "handoff_link", "cid": cid},
        cid=cid,
    )


# ============================================================
# WEBHOOK messages (Meta)
# ============================================================
@app.post("/webhook")
async def receive_webhook(request: Request):
    cid = uuid.uuid4().hex[:10]
    data = await request.json()

    if DEBUG_WEBHOOK:
        print(f"[{cid}] INCOMING RAW:", _j(data)[:3000])

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

        message_id = (msg.get("id") or "").strip()

        # DEDUPE
        if await _dedupe_incoming(wa_id, message_id, cid):
            return {"ok": True}

        contacts = value.get("contacts", [{}]) or [{}]
        profile = (contacts[0].get("profile") or {}) if contacts else {}
        name = (profile.get("name") or "").strip()
        telefone = (contacts[0].get("wa_id") or wa_id).strip()

        user = upsert_user(wa_id, name=name, telefone=telefone)

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
            return {"ok": True}

        if not user_text and choice_id:
            user_text = choice_id

        if not user_text:
            return {"ok": True}

        lower = user_text.lower().strip()

        log_message(
            wa_id,
            "in",
            user_text,
            meta={"src": "whatsapp", "type": msg_type, "cid": cid, "choice_id": choice_id, "message_id": message_id},
        )

        # ============================================================
        # BACK / MENU
        # ============================================================
        if _is_back_trigger(lower):
            ai_state = await get_ai_state(wa_id) or {}
            if bool(ai_state.get("handoff_done")):
                safe_send(
                    wa_id,
                    {
                        "type": "buttons",
                        "text": "Já encaminhei pra Julia ✅\n\nQuer preencher o briefing novamente ou falar com ela agora?",
                        "buttons": [
                            {"id": "BRIEF_RESTART", "title": "Preencher novamente"},
                            {"id": "TALK_HUMAN", "title": "Falar com Julia"},
                        ],
                    },
                    meta={"event": "back_after_handoff", "cid": cid},
                    cid=cid,
                )
                return {"ok": True}

            clear_handoff(wa_id)
            try:
                set_handoff_pending(wa_id, False)
            except Exception:
                pass

            await reset_ai_state(wa_id)
            try:
                clear_flow(wa_id)
            except Exception:
                pass

            flow_resp = handle_mugo_flow(wa_id, "start", choice_id="")
            if flow_resp:
                safe_send(wa_id, flow_resp, meta={"event": "back_to_flow_start", "cid": cid}, cid=cid)
                return {"ok": True}

            safe_send(wa_id, _menu_fallback_text(), meta={"event": "back_to_menu_fallback", "cid": cid}, cid=cid)
            return {"ok": True}

        # ============================================================
        # Botões pós-handoff (tratados aqui)
        # ============================================================
        if (choice_id or user_text) in ("BRIEF_RESTART", "brief_restart"):
            try:
                clear_flow(wa_id)
            except Exception:
                pass

            flow_resp = handle_mugo_flow(wa_id, "start", choice_id="")
            if flow_resp:
                safe_send(wa_id, flow_resp, meta={"event": "brief_restart", "cid": cid}, cid=cid)
                return {"ok": True}

            safe_send(wa_id, _menu_fallback_text(), meta={"event": "brief_restart_fallback", "cid": cid}, cid=cid)
            return {"ok": True}

        if (choice_id or user_text) in ("TALK_HUMAN", "talk_human"):
            st = await get_ai_state(wa_id) or {}
            topic = (st.get("handoff_topic") or "Lead (pós-bot)").strip()[:100]
            summary = (st.get("handoff_summary") or "").strip()

            if not summary:
                try:
                    hist = get_recent_messages(wa_id, limit=10) or []
                    entradas = [(m.get("text") or "").strip() for m in hist if m.get("direction") == "in"]
                    summary = " | ".join(entradas[-4:])[:600]
                except Exception:
                    summary = ""

            link = _build_handoff_link(topic=topic, wa_id=wa_id, summary=summary)
            safe_send(
                wa_id,
                f"Perfeito. Fala com a Julia por aqui:\n{link}",
                meta={"event": "talk_human_link", "cid": cid},
                cid=cid,
            )
            return {"ok": True}

        # ============================================================
        # FLOW PRIMEIRO (sempre)
        # ============================================================
        flow_input = choice_id or user_text

        if DEBUG_WEBHOOK:
            try:
                cur = get_flow(wa_id) or {}
                print(
                    f"[{cid}] FLOW DEBUG -> input={flow_input} choice_id={choice_id} "
                    f"state={cur.get('state')} data_keys={list((cur.get('data') or {}).keys())}"
                )
            except Exception as e:
                print(f"[{cid}] FLOW DEBUG WARN:", repr(e))

        flow_resp = handle_mugo_flow(wa_id, flow_input, choice_id=choice_id)

        if flow_resp:
            ftype = (flow_resp.get("type") or "").lower().strip()

            if ftype in ("buttons", "text", "list"):
                if not bool(user.get("first_message_sent")):
                    try:
                        mark_first_message_sent(wa_id)
                    except Exception:
                        pass

                ok = safe_send(
                    wa_id,
                    flow_resp,
                    meta={"src": "mugo_flow", "cid": cid, "choice_id": choice_id, "message_id": message_id},
                    cid=cid,
                )
                if not ok and ftype in ("buttons", "list"):
                    safe_send(wa_id, _menu_fallback_text(), meta={"event": "flow_menu_fallback", "cid": cid}, cid=cid)
                return {"ok": True}

            if ftype == "handoff":
                text_to_user = (flow_resp.get("text") or "").strip() or "Perfeito. Vou te direcionar agora."
                topic = (flow_resp.get("topic") or "").strip() or "Lead qualificado"
                summary = (flow_resp.get("summary") or "").strip()

                safe_send(wa_id, text_to_user, meta={"src": "mugo_flow_handoff", "cid": cid}, cid=cid)

                start_handoff_now(
                    wa_id=wa_id,
                    cid=cid,
                    reason="flow_completed",
                    topic=topic,
                    summary=summary,
                    last_text=user_text,
                )

                await mark_handoff_done(wa_id, topic=topic, summary=summary)
                return {"ok": True}

        # ============================================================
        # Se foi clique (interactive) e flow não respondeu: NÃO chama IA
        # ============================================================
        if msg_type == "interactive" and choice_id:
            flow_resp2 = handle_mugo_flow(wa_id, "start", choice_id="")
            if flow_resp2:
                safe_send(wa_id, flow_resp2, meta={"event": "interactive_flow_recover", "cid": cid}, cid=cid)
                return {"ok": True}
            safe_send(wa_id, _menu_fallback_text(), meta={"event": "interactive_fallback_text", "cid": cid}, cid=cid)
            return {"ok": True}

        # ============================================================
        # Se ainda não teve first_message_sent, tenta iniciar flow
        # ============================================================
        if not bool(user.get("first_message_sent")):
            flow_start = handle_mugo_flow(wa_id, "start", choice_id="")
            if flow_start:
                try:
                    mark_first_message_sent(wa_id)
                except Exception:
                    pass
                safe_send(wa_id, flow_start, meta={"event": "auto_flow_start", "cid": cid}, cid=cid)
                return {"ok": True}

        # ============================================================
        # IA NORMAL (texto livre)
        # ============================================================
        result = generate_reply(
            wa_id=wa_id,
            user_message=user_text,
            first_message_sent=True,
            name=name,
            telefone=telefone,
        )

        reply_text = (result.get("reply") or "").strip() or "Em uma frase: qual é o foco agora?"
        handoff_flag = bool(result.get("handoff"))
        handoff_summary = (result.get("handoff_summary") or "").strip()

        safe_send(wa_id, reply_text, meta={"src": "ai", "cid": cid, "message_id": message_id}, cid=cid)

        if handoff_flag:
            topic = "Encaminhado pela IA"
            summary = handoff_summary or user_text

            start_handoff_now(
                wa_id=wa_id,
                cid=cid,
                reason="ai_handoff",
                topic=topic,
                summary=summary,
                last_text=user_text,
            )
            await mark_handoff_done(wa_id, topic=topic, summary=summary)

        return {"ok": True}

    except Exception as e:
        print(f"[{cid}] Erro no webhook:", repr(e))
        if DEBUG_WEBHOOK:
            print(f"[{cid}] PAYLOAD:", _j(data)[:4000])
        return {"ok": True}