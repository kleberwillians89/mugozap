import os
import httpx
from fastapi import HTTPException

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

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


async def get_user_from_token(token: str) -> dict:
    token = (token or "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    if not SUPABASE_URL or not SERVICE_KEY:
        raise HTTPException(status_code=500, detail="Server missing Supabase env")

    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {token}",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers)

    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    return r.json()


def is_allowed_internal_user(user: dict) -> bool:
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


def build_internal_user(user: dict) -> dict:
    user = user or {}
    metadata = user.get("user_metadata") or {}
    app_metadata = user.get("app_metadata") or {}
    email = (user.get("email") or "").strip().lower()

    role = (
        metadata.get("role")
        or app_metadata.get("role")
        or DEFAULT_INTERNAL_ROLE
    )

    return {
        "id": user.get("id"),
        "email": email,
        "name": metadata.get("name") or metadata.get("full_name") or email,
        "role": role,
    }


async def require_internal_user(token: str) -> dict:
    user = await get_user_from_token(token)

    if not is_allowed_internal_user(user):
        raise HTTPException(status_code=403, detail="User not allowed in internal panel")

    return build_internal_user(user)