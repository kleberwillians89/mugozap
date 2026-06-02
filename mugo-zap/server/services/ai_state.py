# mugo-zap/server/services/ai_state.py
import os
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from services.workspace import DEFAULT_WORKSPACE_ID, resolve_workspace_id

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

TABLE = (os.getenv("SUPABASE_TABLE_AI_STATE") or "ai_state").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_wa_id(raw: Any) -> str:
    return re.sub(r"\D+", "", str(raw or ""))


def _short_body(text: str) -> str:
    return (text or "").replace("\n", " ")[:500]


DEFAULT_STATE: Dict[str, Any] = {
    "service_interest": None,
    "intent": None,
    "main_goal": None,
    "desired_result": None,
    "site_scope": None,
    "lead_source": None,
    "current_tools": None,
    "current_status": None,
    "current_problem": None,
    "business_type": None,
    "business_name": None,
    "urgency": None,
    "budget_signal": None,
    "funnel_stage": None,
    "stage": "diagnostico",
    "question_count": 0,
    "repeat_hits": 0,
    "close_score": 0,
    "last_question_key": "",
    "last_question_asked": None,
    "last_question_category": None,
    "next_best_question": None,
    "last_bot_message": "",
    "last_user_message": "",
    "last_user_goal": "",
    "handoff_reason": "",
    "handoff": False,
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
    "primary_track": None,
    "related_needs": [],
    "solution": None,
    "objective": None,
    "pain": None,
    "process": None,
    "follow_up": {},
    "briefing_sent_at": None,
    "briefing_sent_julia": False,
    "briefing_sent_eduarda": False,
    "handoff_sent_at": None,
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
    wa_id = _normalize_wa_id(wa_id)
    workspace_id = _resolve_workspace_id(workspace_id)
    print(f"SALES_STATE_LOAD_KEY wa_id={wa_id or '-'} workspace_id={workspace_id or '-'} table={TABLE}")
    if not wa_id:
        return dict(DEFAULT_STATE)

    if not _is_ready():
        print("SALES_STATE_LOAD_RAW skipped reason=supabase_not_configured")
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
                print(
                    f"SALES_STATE_LOAD_RAW wa_id={wa_id} workspace_id={workspace_id} "
                    f"query_index={index} status={r.status_code} body={_short_body(r.text)}"
                )
                if r.status_code == 200:
                    rows = r.json() or []
                    print(f"SALES_STATE_LOAD_RAW wa_id={wa_id} rows={len(rows)} query_index={index}")
                    break
                if index == 0 and _looks_like_missing_workspace(r.status_code, r.text):
                    continue
                return dict(DEFAULT_STATE)

        if not rows:
            await upsert_ai_state(wa_id, dict(DEFAULT_STATE), workspace_id=workspace_id)
            print(f"SALES_STATE_LOAD_FLATTENED wa_id={wa_id} empty=true")
            return dict(DEFAULT_STATE)

        state = rows[0].get("state") or {}
        merged = _merge_defaults(state)
        print(
            f"SALES_STATE_LOAD_FLATTENED wa_id={wa_id} "
            f"state={json.dumps({k: merged.get(k) for k in ['service_interest', 'last_question_category', 'site_scope', 'lead_source', 'current_status']}, ensure_ascii=False)}"
        )
        return merged

    except Exception as e:
        print(f"SALES_STATE_LOAD_RAW wa_id={wa_id} error={type(e).__name__}:{str(e)[:300]}")
        return dict(DEFAULT_STATE)


async def upsert_ai_state(wa_id: str, state: Dict[str, Any], workspace_id: Optional[str] = "") -> Dict[str, Any]:
    wa_id = _normalize_wa_id(wa_id)
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return dict(DEFAULT_STATE)

    merged = _merge_defaults(state or {})
    print(
        f"SALES_STATE_SAVE_PAYLOAD wa_id={wa_id} workspace_id={workspace_id} "
        f"state={json.dumps({k: merged.get(k) for k in ['service_interest', 'last_question_category', 'last_question_asked', 'site_scope', 'lead_source', 'current_status', 'current_tools']}, ensure_ascii=False)[:900]}"
    )

    if not _is_ready():
        print("SALES_STATE_SAVE_RESULT skipped reason=supabase_not_configured")
        return merged

    payload = {
        "workspace_id": workspace_id,
        "wa_id": wa_id,
        "state": merged,
        "updated_at": merged["updated_at"],
    }
    legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}

    workspace_filter = f"workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    legacy_filter = f"wa_id=eq.{wa_id}"

    async def _patch(client: httpx.AsyncClient, query: str, body: Dict[str, Any]) -> httpx.Response:
        return await client.patch(
            f"{SUPABASE_URL}/rest/v1/{TABLE}?{query}",
            headers={**_headers(), "Prefer": "return=representation"},
            content=json.dumps(body, ensure_ascii=False),
        )

    async def _insert(client: httpx.AsyncClient, body: Dict[str, Any]) -> httpx.Response:
        return await client.post(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            headers={**_headers(), "Prefer": "return=representation"},
            content=json.dumps(body, ensure_ascii=False),
        )

    def _state_from_response(r: httpx.Response) -> Dict[str, Any] | None:
        if r.status_code not in (200, 201):
            return None
        rows = r.json() or []
        if rows and isinstance(rows, list):
            return _merge_defaults(rows[0].get("state") or {})
        return None

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await _patch(client, workspace_filter, payload)
            print(f"SALES_STATE_SAVE_RESULT op=patch_workspace status={r.status_code} body={_short_body(r.text)}")
            state_out = _state_from_response(r)
            if state_out:
                return state_out

            if _looks_like_missing_workspace(r.status_code, r.text):
                r = await _patch(client, legacy_filter, legacy_payload)
                print(f"SALES_STATE_SAVE_RESULT op=patch_legacy status={r.status_code} body={_short_body(r.text)}")
                state_out = _state_from_response(r)
                if state_out:
                    return state_out
                r = await _insert(client, legacy_payload)
                print(f"SALES_STATE_SAVE_RESULT op=insert_legacy status={r.status_code} body={_short_body(r.text)}")
                state_out = _state_from_response(r)
                return state_out or merged

            r = await _insert(client, payload)
            print(f"SALES_STATE_SAVE_RESULT op=insert_workspace status={r.status_code} body={_short_body(r.text)}")
            state_out = _state_from_response(r)
            if state_out:
                return state_out

            r = await _patch(client, legacy_filter, legacy_payload)
            print(f"SALES_STATE_SAVE_RESULT op=patch_legacy_after_insert status={r.status_code} body={_short_body(r.text)}")
            state_out = _state_from_response(r)
            if state_out:
                return state_out

        return merged

    except Exception as e:
        print(f"SALES_STATE_SAVE_RESULT wa_id={wa_id} error={type(e).__name__}:{str(e)[:300]}")
        return merged


async def reset_ai_state(wa_id: str, workspace_id: Optional[str] = "") -> Dict[str, Any]:
    return await upsert_ai_state(wa_id, dict(DEFAULT_STATE), workspace_id=workspace_id)
