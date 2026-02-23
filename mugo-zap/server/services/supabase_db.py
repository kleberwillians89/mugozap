# services/supabase_db.py
import os
import requests
from typing import Any, Dict, List, Optional

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    # Não quebra import: você decide no runtime se usa supabase ou local
    pass

def _headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

def supabase_get(path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()

def supabase_post(path: str, payload: Any) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.post(url, headers=_headers(), json=payload, timeout=20)
    r.raise_for_status()
    return r.json() if r.text else {}