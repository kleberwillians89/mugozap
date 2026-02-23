# services/ai_state.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

TABLE = "ai_state"

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
    "updated_at": "",
}

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _headers():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

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
        merged = dict(DEFAULT_STATE)
        merged.update(state)
        merged["updated_at"] = _now_iso()
        return merged

async def upsert_ai_state(wa_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return dict(DEFAULT_STATE)

    merged = dict(DEFAULT_STATE)
    merged.update(state or {})
    merged["updated_at"] = _now_iso()

    payload = {"wa_id": wa_id, "state": merged, "updated_at": merged["updated_at"]}
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=wa_id"

    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.post(
            url,
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            data=json.dumps(payload),
        )
        if r.status_code not in (200, 201):
            return merged

        rows = r.json() or []
        if rows and isinstance(rows, list):
            state_out = (rows[0].get("state") or {})
            out = dict(DEFAULT_STATE)
            out.update(state_out)
            out["updated_at"] = _now_iso()
            return out

    return merged

async def reset_ai_state(wa_id: str) -> Dict[str, Any]:
    return await upsert_ai_state(wa_id, dict(DEFAULT_STATE))