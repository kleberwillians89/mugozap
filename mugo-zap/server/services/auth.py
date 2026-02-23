import os
import httpx
from fastapi import HTTPException

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

async def get_user_from_token(token: str) -> dict:
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