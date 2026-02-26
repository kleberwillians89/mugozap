# services/ai_state.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

TABLE = "ai_state"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Estado default (inclui os novos campos que o app.py usa)
DEFAULT_STATE: Dict[str, Any] = {
    "intent": "",
    "stage": "diagnostico",
    "question_count": 0,
    "repeat_hits": 0,
    "close_score": 0,
    "last_question_key": "",
    "last_bot_message": "",
    "last_user_message": "",
    "last_user_goal": "",
    "handoff_reason": "",

    # ✅ DEDUPE
    "last_in_msg_id": "",
    "last_in_at": "",

    # ✅ VOLTAR PÓS-HANDOFF
    "handoff_done": False,
    "handoff_done_at": "",
    "handoff_topic": "",
    "handoff_summary": "",

    # meta
    "updated_at": "",
}

def _headers() -> Dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

def _merge_defaults(state: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULT_STATE)
    if isinstance(state, dict):
        merged.update(state)
    merged["updated_at"] = _now_iso()
    return merged

async def get_ai_state(wa_id: str) -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return dict(DEFAULT_STATE)

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?wa_id=eq.{wa_id}&select=state"

    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(url, headers=_headers())
        if r.status_code != 200:
            return dict(DEFAULT_STATE)

        rows = r.json() or []
        if not rows:
            # cria default
            await upsert_ai_state(wa_id, dict(DEFAULT_STATE))
            return dict(DEFAULT_STATE)

        state = rows[0].get("state") or {}
        return _merge_defaults(state)

async def upsert_ai_state(wa_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return dict(DEFAULT_STATE)

    merged = _merge_defaults(state or {})

    payload = {
        "wa_id": wa_id,
        "state": merged,
        "updated_at": merged["updated_at"],
    }

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=wa_id"

    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.post(
            url,
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            content=json.dumps(payload, ensure_ascii=False),
        )

        # mesmo se não retornar representação, a gente segue com o merged
        if r.status_code not in (200, 201):
            return merged

        rows = r.json() or []
        if rows and isinstance(rows, list):
            state_out = rows[0].get("state") or {}
            return _merge_defaults(state_out)

    return merged

async def reset_ai_state(wa_id: str) -> Dict[str, Any]:
    # reset total (zera inclusive handoff_done)
    return await upsert_ai_state(wa_id, dict(DEFAULT_STATE))