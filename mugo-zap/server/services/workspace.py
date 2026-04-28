import os
import json
from typing import Any, Dict

import httpx

DEFAULT_WORKSPACE_ID = (os.getenv("DEFAULT_WORKSPACE_ID") or "workspace-mugo-default").strip()
DEFAULT_WORKSPACE_NAME = (os.getenv("DEFAULT_WORKSPACE_NAME") or "Mugo").strip()
DEFAULT_WORKSPACE_SLUG = (os.getenv("DEFAULT_WORKSPACE_SLUG") or "mugo").strip()
WORKSPACES_TABLE = (os.getenv("WORKSPACES_TABLE") or "workspaces").strip()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()


def build_default_workspace() -> Dict[str, str]:
    return {
        "id": DEFAULT_WORKSPACE_ID,
        "name": DEFAULT_WORKSPACE_NAME,
        "slug": DEFAULT_WORKSPACE_SLUG,
    }


def _is_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers(extra: Dict[str, str] | None = None) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def resolve_workspace_id(
    *,
    explicit_workspace_id: str = "",
    user: Dict[str, Any] | None = None,
) -> str:
    explicit_workspace_id = (explicit_workspace_id or "").strip()
    if explicit_workspace_id:
        return explicit_workspace_id

    user = user or {}
    metadata = user.get("user_metadata") or {}
    app_metadata = user.get("app_metadata") or {}

    workspace_id = (
        metadata.get("workspace_id")
        or app_metadata.get("workspace_id")
        or user.get("workspace_id")
        or DEFAULT_WORKSPACE_ID
    )

    return (workspace_id or DEFAULT_WORKSPACE_ID).strip()


async def ensure_default_workspace() -> Dict[str, Any]:
    workspace = build_default_workspace()

    if not _is_ready():
        return workspace

    url = f"{SUPABASE_URL}/rest/v1/{WORKSPACES_TABLE}?on_conflict=id"
    payload = {
        **workspace,
        "is_default": True,
    }

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                url,
                headers=_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
                content=json.dumps(payload, ensure_ascii=False),
            )

        if resp.status_code in (200, 201):
            rows = resp.json() or []
            if rows:
                return rows[0] or workspace
    except Exception:
        pass

    return workspace
