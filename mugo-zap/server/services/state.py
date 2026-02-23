# mugo-zap/server/services/state.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

# Tabelas (ajustáveis por env)
WA_USERS_TABLE = (os.getenv("WA_USERS_TABLE") or "whatsapp_users").strip()
WA_MESSAGES_TABLE = (os.getenv("WA_MESSAGES_TABLE") or "whatsapp_messages").strip()
WA_TASKS_TABLE = (os.getenv("WA_TASKS_TABLE") or "whatsapp_tasks").strip()


# ============================================================
# Helpers
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers() -> Dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _safe_json(v: Any, fallback: Any):
    try:
        if v is None:
            return fallback
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str) and v.strip():
            return json.loads(v)
    except Exception:
        pass
    return fallback


def _get(url: str) -> httpx.Response:
    with httpx.Client(timeout=12) as client:
        return client.get(url, headers=_headers())


def _post(url: str, payload: dict, prefer: str = "return=representation") -> httpx.Response:
    with httpx.Client(timeout=12) as client:
        return client.post(
            url,
            headers={**_headers(), "Prefer": prefer},
            data=json.dumps(payload),
        )


def _patch(url: str, payload: dict, prefer: str = "return=representation") -> httpx.Response:
    with httpx.Client(timeout=12) as client:
        return client.patch(
            url,
            headers={**_headers(), "Prefer": prefer},
            data=json.dumps(payload),
        )


# ============================================================
# USERS / CONTACTS
# ============================================================
def upsert_user(wa_id: str, name: str = "", telefone: str = "", **extra) -> Dict[str, Any]:
    """
    Cria/atualiza utilizador no Supabase (whatsapp_users).
    Retorna um dict com (no mínimo):
      - wa_id
      - first_message_sent (bool)
      - handoff_active (bool)
    """
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return {"wa_id": "", "first_message_sent": False, "handoff_active": False}

    payload: Dict[str, Any] = {
        "wa_id": wa_id,
        "name": (name or "").strip(),
        "telefone": (telefone or "").strip(),
    }

    # campos opcionais (se existirem na tabela)
    for k in [
        "first_message_sent",
        "handoff_active",
        "handoff_pending",
        "handoff_topic",
        "stage",
        "notes",
        "tags",
        "owner",
        "last_in_at",
        "last_out_at",
        "last_text",
        "last_at",
        "last_message",
        # LEAD INTELLIGENCE (opcional)
        "lead_score",
        "lead_temperature",
        "lead_theme",
        "lead_stage",
        "priority",
    ]:
        if k in extra and extra[k] is not None:
            payload[k] = extra[k]

    url = f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?on_conflict=wa_id"

    # UPSERT merge
    try:
        r = _post(url, payload, prefer="resolution=merge-duplicates,return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            if rows:
                row = rows[0] or {}
                return {
                    "wa_id": row.get("wa_id") or wa_id,
                    "first_message_sent": bool(row.get("first_message_sent") or False),
                    "handoff_active": bool(row.get("handoff_active") or False),
                    **row,
                }
        return {"_error": r.text, **payload}
    except Exception as e:
        return {"_error": str(e), **payload}

    # fallback: GET (não alcança por causa do return acima, mas mantive seu padrão)
    try:
        g = _get(f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?wa_id=eq.{wa_id}&select=*")
        if g.status_code == 200:
            rows = g.json() or []
            if rows:
                row = rows[0] or {}
                return {
                    "wa_id": row.get("wa_id") or wa_id,
                    "first_message_sent": bool(row.get("first_message_sent") or False),
                    "handoff_active": bool(row.get("handoff_active") or False),
                    **row,
                }
    except Exception:
        pass

    return {"wa_id": wa_id, "first_message_sent": False, "handoff_active": False}


def mark_first_message_sent(wa_id: str):
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return {"ok": False}
    upsert_user(wa_id, first_message_sent=True)
    return {"ok": True}


def set_stage(wa_id: str, stage: str):
    return upsert_user(wa_id, stage=stage)


def set_notes(wa_id: str, notes: str):
    return upsert_user(wa_id, notes=notes)


def set_tags(wa_id: str, tags: Any):
    # aceita list/str/dict -> salva como json/string
    t = tags
    if isinstance(tags, (list, dict)):
        t = tags
    elif isinstance(tags, str):
        t = tags.strip()
    return upsert_user(wa_id, tags=t)


# ============================================================
# HANDOFF
# ============================================================
def set_handoff_pending(wa_id: str, pending: bool):
    return upsert_user(wa_id, handoff_pending=bool(pending))


def set_handoff_topic(wa_id: str, topic: str):
    return upsert_user(wa_id, handoff_topic=(topic or "").strip(), handoff_active=True)


def clear_handoff(wa_id: str):
    return upsert_user(wa_id, handoff_active=False, handoff_pending=False, handoff_topic="")


# ============================================================
# LEAD INTELLIGENCE
# ============================================================
def update_lead_intelligence(wa_id: str, score: int, temperature: str, theme: str) -> Dict[str, Any]:
    """
    Atualiza score, temperatura, tema, estágio e prioridade no whatsapp_users.
    Sem updated_at para evitar PGRST204 em tabelas sem coluna.
    """
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return {"ok": False, "detail": "missing wa_id"}

    score_i = int(score or 0)

    # estágio + prioridade
    if score_i >= 70:
        lead_stage = "quente"
        priority = 3
    elif score_i >= 40:
        lead_stage = "qualificado"
        priority = 2
    else:
        lead_stage = "novo"
        priority = 1

    payload = {
        "lead_score": score_i,
        "lead_temperature": (temperature or "frio"),
        "lead_theme": (theme or "indefinido"),
        "lead_stage": lead_stage,
        "priority": priority,
        # opcional: jogar tema em tags (se você quiser)
        # "tags": [theme] if theme and theme != "indefinido" else None,
    }

    # remove keys com None
    payload = {k: v for k, v in payload.items() if v is not None}

    url = f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?wa_id=eq.{wa_id}"

    try:
        r = _patch(url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# MESSAGES
# ============================================================
def log_message(wa_id: str, direction: str, text: str, meta: Optional[dict] = None) -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    direction = (direction or "").strip()
    text = (text or "").strip()
    if not wa_id or not direction or not text:
        return {"ok": False}

    payload: Dict[str, Any] = {
        "wa_id": wa_id,
        "direction": direction,
        "text": text,
        "created_at": _now_iso(),
    }

    if meta is not None:
        payload["meta"] = meta

    url = f"{SUPABASE_URL}/rest/v1/{WA_MESSAGES_TABLE}"

    try:
        r = _post(url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_recent_messages(wa_id: str, limit: int = 60) -> List[Dict[str, Any]]:
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return []

    url = (
        f"{SUPABASE_URL}/rest/v1/{WA_MESSAGES_TABLE}"
        f"?wa_id=eq.{wa_id}&select=*&order=created_at.desc&limit={int(limit)}"
    )
    try:
        r = _get(url)
        if r.status_code == 200:
            rows = r.json() or []
            return list(reversed(rows))
    except Exception:
        pass
    return []


def list_conversations(limit: int = 200) -> List[Dict[str, Any]]:
    limit = int(limit or 200)

    users: List[Dict[str, Any]] = []
    users_url_candidates = [
        # NOVO: prioridade/score primeiro (se colunas existirem)
        f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?select=*&order=priority.desc,lead_score.desc,last_at.desc.nullslast&limit={limit}",
        # fallbacks antigos
        f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?select=*&order=last_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?select=*&order=updated_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?select=*&order=created_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{WA_USERS_TABLE}?select=*&limit={limit}",
    ]

    try:
        for uurl in users_url_candidates:
            ur = _get(uurl)
            if ur.status_code == 200:
                users = ur.json() or []
                break
    except Exception:
        users = []

    last_by: Dict[str, Dict[str, Any]] = {}
    totals_by: Dict[str, int] = {}

    try:
        msg_url = (
            f"{SUPABASE_URL}/rest/v1/{WA_MESSAGES_TABLE}"
            f"?select=wa_id,text,created_at,direction&order=created_at.desc&limit={min(5000, limit*25)}"
        )
        mr = _get(msg_url)
        if mr.status_code == 200:
            rows = mr.json() or []
            for m in rows:
                wid = (m.get("wa_id") or "").strip()
                if not wid:
                    continue
                totals_by[wid] = totals_by.get(wid, 0) + 1
                if wid not in last_by:
                    last_by[wid] = m
    except Exception:
        pass

    if not users:
        items: List[Dict[str, Any]] = []
        for wa_id, last in last_by.items():
            items.append({
                "wa_id": wa_id,
                "name": "",
                "telefone": "",
                "stage": "",
                "notes": "",
                "tags": "",
                "handoff_active": False,
                "handoff_topic": "",
                "first_message_sent": False,
                "updated_at": "",
                "last_message": (last.get("text") or ""),
                "last_message_at": (last.get("created_at") or ""),
                "last_message_dir": (last.get("direction") or ""),
                "total_messages": totals_by.get(wa_id, 0),
                # lead fields default
                "lead_score": 0,
                "lead_temperature": "frio",
                "lead_theme": "indefinido",
                "lead_stage": "novo",
                "priority": 0,
            })
        return items[:limit]

    items: List[Dict[str, Any]] = []
    for u in users:
        wa_id = (u.get("wa_id") or "").strip()
        if not wa_id:
            continue

        last = last_by.get(wa_id) or {}

        items.append({
            "wa_id": wa_id,
            "name": u.get("name") or "",
            "telefone": u.get("telefone") or "",
            "stage": u.get("stage") or "",
            "notes": u.get("notes") or "",
            "tags": u.get("tags") if u.get("tags") is not None else "",
            "handoff_active": bool(u.get("handoff_active") or False),
            "handoff_topic": u.get("handoff_topic") or "",
            "first_message_sent": bool(u.get("first_message_sent") or False),
            "updated_at": u.get("last_at") or u.get("updated_at") or u.get("created_at") or "",
            "last_message": (last.get("text") or (u.get("last_text") or u.get("last_message") or "")),
            "last_message_at": (last.get("created_at") or (u.get("last_at") or "")),
            "last_message_dir": (last.get("direction") or ""),
            "total_messages": totals_by.get(wa_id, 0),
            # lead fields (se existirem)
            "lead_score": u.get("lead_score") or 0,
            "lead_temperature": u.get("lead_temperature") or "frio",
            "lead_theme": u.get("lead_theme") or "indefinido",
            "lead_stage": u.get("lead_stage") or "novo",
            "priority": u.get("priority") or 0,
        })

    return items


# ============================================================
# TASKS
# ============================================================
def create_task(wa_id: str, title: str, due_at_iso: str) -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    title = (title or "").strip()
    due_at_iso = (due_at_iso or "").strip()

    payload = {
        "wa_id": wa_id,
        "title": title,
        "due_at": due_at_iso,
        "status": "open",
        "created_at": _now_iso(),
        # NÃO mandar updated_at
    }
    url = f"{SUPABASE_URL}/rest/v1/{WA_TASKS_TABLE}"
    try:
        r = _post(url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return rows[0] if rows else payload
        return {"_error": r.text, **payload}
    except Exception as e:
        return {"_error": str(e), **payload}


def list_tasks(
    status: str = "open",
    due_before: Optional[str] = None,
    wa_id: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    filters = ["select=*", "order=due_at.asc", f"limit={int(limit)}"]
    if status:
        filters.append(f"status=eq.{status}")
    if wa_id:
        filters.append(f"wa_id=eq.{wa_id}")
    if due_before:
        filters.append(f"due_at=lt.{due_before}")
    url = f"{SUPABASE_URL}/rest/v1/{WA_TASKS_TABLE}?" + "&".join(filters)
    try:
        r = _get(url)
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def done_task(task_id: str) -> Dict[str, Any]:
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "detail": "missing id"}

    url = f"{SUPABASE_URL}/rest/v1/{WA_TASKS_TABLE}?id=eq.{task_id}"
    payload = {
        "status": "done",
        "done_at": _now_iso(),
        # NÃO mandar updated_at
    }
    try:
        r = _patch(url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_task(task_id: str, **fields) -> Dict[str, Any]:
    """
    Atualiza task (drag&drop na agenda).
    Aceita: due_at, title, status, wa_id
    """
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "detail": "missing id"}

    payload: Dict[str, Any] = {}
    for k in ("due_at", "title", "status", "wa_id"):
        if k in fields and fields[k] is not None:
            payload[k] = fields[k]

    if not payload:
        return {"ok": False, "detail": "no fields to update"}

    url = f"{SUPABASE_URL}/rest/v1/{WA_TASKS_TABLE}?id=eq.{task_id}"
    try:
        r = _patch(url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}