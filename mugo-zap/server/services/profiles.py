import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from services.workspace import DEFAULT_WORKSPACE_ID, resolve_workspace_id

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
PROFILES_TABLE = (os.getenv("SUPABASE_PROFILES_TABLE") or "profiles").strip()

ROLE_ADMIN = "admin"
ROLE_GESTOR = "gestor"
ROLE_ATENDIMENTO = "atendimento"
VALID_ROLES = {ROLE_ADMIN, ROLE_GESTOR, ROLE_ATENDIMENTO}

_TIMEOUT = httpx.Timeout(connect=6.0, read=12.0, write=12.0, pool=12.0)
_CLIENT = httpx.Client(timeout=_TIMEOUT, headers={"Content-Type": "application/json"})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_role(value: Any) -> str:
    role = str(value or "").strip().lower()
    if role in {"admin", "administrator", "painel"}:
        return ROLE_ADMIN
    if role in {"gestor", "manager", "gerente"}:
        return ROLE_GESTOR
    if role in {"atendimento", "attendant", "staff", "user", "operador"}:
        return ROLE_ATENDIMENTO
    return ROLE_ATENDIMENTO


def profile_display_name(user: Dict[str, Any] | None) -> str:
    user = user or {}
    return str(user.get("name") or user.get("email") or user.get("id") or "").strip()


def can_manage_users(user: Dict[str, Any] | None) -> bool:
    return normalize_role((user or {}).get("role")) == ROLE_ADMIN


def can_manage_all_conversations(user: Dict[str, Any] | None) -> bool:
    return normalize_role((user or {}).get("role")) in {ROLE_ADMIN, ROLE_GESTOR}


def can_access_billing(user: Dict[str, Any] | None) -> bool:
    return normalize_role((user or {}).get("role")) in {ROLE_ADMIN, ROLE_GESTOR}


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    base = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        base.update(extra)
    return base


def _profile_payload_from_user(user: Dict[str, Any], workspace_id: str = "") -> Dict[str, Any]:
    user = user or {}
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id, user=user) or DEFAULT_WORKSPACE_ID
    return {
        "auth_user_id": user.get("id"),
        "name": profile_display_name(user),
        "email": str(user.get("email") or "").strip().lower(),
        "role": normalize_role(user.get("role")),
        "active": True,
        "workspace_id": workspace_id,
        "updated_at": now_iso(),
    }


def _normalize_profile(row: Dict[str, Any], fallback_user: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fallback_user = fallback_user or {}
    row = dict(row or {})
    return {
        "id": row.get("id") or row.get("auth_user_id") or fallback_user.get("id"),
        "auth_user_id": row.get("auth_user_id") or fallback_user.get("id"),
        "name": row.get("name") or fallback_user.get("name") or row.get("email") or fallback_user.get("email") or "",
        "email": str(row.get("email") or fallback_user.get("email") or "").strip().lower(),
        "role": normalize_role(row.get("role") or fallback_user.get("role")),
        "active": bool(row.get("active", True)),
        "workspace_id": row.get("workspace_id") or fallback_user.get("workspace_id") or DEFAULT_WORKSPACE_ID,
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def get_profile_for_user(user: Dict[str, Any], workspace_id: str = "") -> Dict[str, Any]:
    if not user:
        return {}

    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id, user=user) or DEFAULT_WORKSPACE_ID
    auth_user_id = str(user.get("id") or "").strip()
    email = str(user.get("email") or "").strip().lower()

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or (not auth_user_id and not email):
        return _normalize_profile(_profile_payload_from_user(user, workspace_id), fallback_user=user)

    filters = []
    if auth_user_id:
        filters.append(f"auth_user_id=eq.{auth_user_id}")
    if email:
        filters.append(f"email=eq.{email}")

    for filter_expr in filters:
        url = (
            f"{SUPABASE_URL}/rest/v1/{PROFILES_TABLE}"
            f"?workspace_id=eq.{workspace_id}&{filter_expr}&select=*&limit=1"
        )
        try:
            resp = _CLIENT.get(url, headers=_headers())
            if resp.status_code == 200:
                rows = resp.json() or []
                if rows:
                    return _normalize_profile(rows[0], fallback_user=user)
            elif resp.status_code in {404, 406} or "does not exist" in resp.text.lower():
                break
        except Exception:
            break

    payload = _profile_payload_from_user(user, workspace_id)
    if auth_user_id:
        try:
            url = f"{SUPABASE_URL}/rest/v1/{PROFILES_TABLE}?on_conflict=auth_user_id"
            resp = _CLIENT.post(
                url,
                headers=_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
                content=json.dumps(payload, ensure_ascii=False),
            )
            if resp.status_code in (200, 201):
                rows = resp.json() or []
                if rows:
                    return _normalize_profile(rows[0], fallback_user=user)
        except Exception:
            pass

    return _normalize_profile(payload, fallback_user=user)


def list_profiles(workspace_id: str = "") -> List[Dict[str, Any]]:
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID
    url = (
        f"{SUPABASE_URL}/rest/v1/{PROFILES_TABLE}"
        f"?workspace_id=eq.{workspace_id}&select=*&order=name.asc"
    )
    resp = _CLIENT.get(url, headers=_headers())
    if resp.status_code != 200:
        text = resp.text or ""
        if resp.status_code == 404 and (
            "PGRST205" in text
            or "Could not find the table" in text
            or "does not exist" in text.lower()
        ):
            return []
        raise RuntimeError(resp.text)
    return [_normalize_profile(row) for row in (resp.json() or [])]


def create_profile(payload: Dict[str, Any], workspace_id: str = "") -> Dict[str, Any]:
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID
    email = str(payload.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Missing email")

    auth_user_id = str(payload.get("auth_user_id") or "").strip()
    password = str(payload.get("password") or "").strip()

    if not auth_user_id and password:
        admin_payload = {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "name": str(payload.get("name") or email).strip(),
                "role": normalize_role(payload.get("role")),
                "workspace_id": workspace_id,
            },
        }
        resp = _CLIENT.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_headers(),
            content=json.dumps(admin_payload, ensure_ascii=False),
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(resp.text)
        auth_user_id = (resp.json() or {}).get("id") or ""

    profile = {
        "auth_user_id": auth_user_id or None,
        "name": str(payload.get("name") or email).strip(),
        "email": email,
        "role": normalize_role(payload.get("role")),
        "active": bool(payload.get("active", True)),
        "workspace_id": workspace_id,
        "updated_at": now_iso(),
    }

    resp = _CLIENT.post(
        f"{SUPABASE_URL}/rest/v1/{PROFILES_TABLE}",
        headers=_headers({"Prefer": "return=representation"}),
        content=json.dumps(profile, ensure_ascii=False),
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(resp.text)
    rows = resp.json() or []
    return _normalize_profile(rows[0] if rows else profile)


def update_profile(profile_id: str, payload: Dict[str, Any], workspace_id: str = "") -> Dict[str, Any]:
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID
    fields: Dict[str, Any] = {"updated_at": now_iso()}
    if "name" in payload:
        fields["name"] = str(payload.get("name") or "").strip()
    if "role" in payload:
        fields["role"] = normalize_role(payload.get("role"))
    if "active" in payload:
        fields["active"] = bool(payload.get("active"))

    if len(fields) == 1:
        raise ValueError("No fields to update")

    safe_id = str(profile_id or "").strip()
    url = f"{SUPABASE_URL}/rest/v1/{PROFILES_TABLE}?workspace_id=eq.{workspace_id}&id=eq.{safe_id}"
    resp = _CLIENT.patch(
        url,
        headers=_headers({"Prefer": "return=representation"}),
        content=json.dumps(fields, ensure_ascii=False),
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(resp.text)
    rows = resp.json() if resp.content else []
    return _normalize_profile(rows[0] if rows else {"id": safe_id, **fields, "workspace_id": workspace_id})
