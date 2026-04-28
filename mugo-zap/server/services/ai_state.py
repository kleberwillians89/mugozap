# mugo-zap/server/services/ai_state.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from services.workspace import DEFAULT_WORKSPACE_ID, resolve_workspace_id

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

TABLE = "ai_state"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    "last_in_msg_id": "",
    "last_in_at": "",
    "handoff_done": False,
    "handoff_done_at": "",
    "handoff_topic": "",
    "handoff_summary": "",
    "memory_summary": "",
    "memory_theme": "",
    "memory_goal": "",
    "memory_notes": [],
    "lead_temperature": "",
    "next_action": "",
    "meeting_suggested": False,
    "briefing_ready": False,
    "selected_service": "",
    "selected_service_id": "",
    "suggested_tags": [],
    "lead_fields": {},
    "briefing": {},
    "follow_up": {},
    "briefing_sent_at": "",
    "briefing_sent_julia": False,
    "briefing_sent_eduarda": False,
    "handoff_sent_at": "",
    "followups_sent": {},
    "last_followup_stage": "",
    "last_followup_at": "",
    "updated_at": "",
}


def _is_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> Dict[str, str]:
    if not _is_ready():
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _merge_defaults(state: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = dict(DEFAULT_STATE)
    if isinstance(state, dict):
        merged.update(state)
    merged["updated_at"] = _now_iso()
    return merged


def _looks_like_missing_workspace(status_code: int, body: str = "") -> bool:
    text = (body or "").lower()
    return status_code >= 400 and "workspace_id" in text


def _resolve_workspace_id(workspace_id: Optional[str] = "") -> str:
    return resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID


async def get_ai_state(wa_id: str, workspace_id: Optional[str] = "") -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return dict(DEFAULT_STATE)

    if not _is_ready():
        return dict(DEFAULT_STATE)

    urls = [
        f"{SUPABASE_URL}/rest/v1/{TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}&select=state",
        f"{SUPABASE_URL}/rest/v1/{TABLE}?wa_id=eq.{wa_id}&select=state",
    ]

    try:
        rows = []
        async with httpx.AsyncClient(timeout=12) as client:
            for index, url in enumerate(urls):
                r = await client.get(url, headers=_headers())
                if r.status_code == 200:
                    rows = r.json() or []
                    break
                if index == 0 and _looks_like_missing_workspace(r.status_code, r.text):
                    continue
                return dict(DEFAULT_STATE)

        if not rows:
            await upsert_ai_state(wa_id, dict(DEFAULT_STATE), workspace_id=workspace_id)
            return dict(DEFAULT_STATE)

        state = rows[0].get("state") or {}
        return _merge_defaults(state)

    except Exception:
        return dict(DEFAULT_STATE)


async def upsert_ai_state(wa_id: str, state: Dict[str, Any], workspace_id: Optional[str] = "") -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return dict(DEFAULT_STATE)

    merged = _merge_defaults(state or {})

    if not _is_ready():
        return merged

    payload = {
        "workspace_id": workspace_id,
        "wa_id": wa_id,
        "state": merged,
        "updated_at": merged["updated_at"],
    }
    legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=workspace_id,wa_id"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=wa_id"

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.post(
                url,
                headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
                content=json.dumps(payload, ensure_ascii=False),
            )

            if _looks_like_missing_workspace(r.status_code, r.text):
                r = await client.post(
                    legacy_url,
                    headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
                    content=json.dumps(legacy_payload, ensure_ascii=False),
                )

        if r.status_code not in (200, 201):
            return merged

        rows = r.json() or []
        if rows and isinstance(rows, list):
            state_out = rows[0].get("state") or {}
            return _merge_defaults(state_out)

        return merged

    except Exception:
        return merged


async def reset_ai_state(wa_id: str, workspace_id: Optional[str] = "") -> Dict[str, Any]:
    return await upsert_ai_state(wa_id, dict(DEFAULT_STATE), workspace_id=workspace_id)
