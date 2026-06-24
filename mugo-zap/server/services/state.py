import os
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from services.workspace import DEFAULT_WORKSPACE_ID, resolve_workspace_id

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

CONVERSATIONS_TABLE = (
    os.getenv("SUPABASE_TABLE_CONVERSATIONS")
    or os.getenv("WA_CONVERSATIONS_TABLE")
    or "whatsapp_conversations"
).strip()
USERS_TABLE = (
    os.getenv("SUPABASE_TABLE_USERS")
    or os.getenv("WA_USERS_TABLE")
    or "whatsapp_users"
).strip()
MESSAGES_TABLE = (
    os.getenv("SUPABASE_TABLE_MESSAGES")
    or os.getenv("WA_MESSAGES_TABLE")
    or "whatsapp_messages"
).strip()
TASKS_TABLE = (
    os.getenv("SUPABASE_TABLE_TASKS")
    or os.getenv("WA_TASKS_TABLE")
    or "whatsapp_tasks"
).strip()
FLOW_TABLE = (
    os.getenv("SUPABASE_TABLE_FLOW_STATE")
    or os.getenv("WA_FLOW_STATE_TABLE")
    or "whatsapp_flow_state"
).strip()

_TIMEOUT = httpx.Timeout(connect=6.0, read=12.0, write=12.0, pool=12.0)
_CLIENT = httpx.Client(timeout=_TIMEOUT, headers={"Content-Type": "application/json"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_wa_id(raw: Any) -> str:
    return re.sub(r"\D+", "", str(raw or ""))


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


def _resolve_workspace_id(workspace_id: str = "") -> str:
    return resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID


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


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _merge_non_empty(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if _has_value(value) or not _has_value(merged.get(key)):
            merged[key] = value
    return merged


def _normalize_tags(v: Any) -> List[str]:
    if v is None:
        return []

    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []

        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        return [x.strip() for x in s.split(",") if x.strip()]

    return []


def _get(url: str) -> httpx.Response:
    return _CLIENT.get(url, headers=_headers())


def _post(url: str, payload: dict, prefer: str = "return=representation") -> httpx.Response:
    return _CLIENT.post(
        url,
        headers=_headers({"Prefer": prefer}),
        content=json.dumps(payload, ensure_ascii=False),
    )


def _patch(url: str, payload: dict, prefer: str = "return=representation") -> httpx.Response:
    return _CLIENT.patch(
        url,
        headers=_headers({"Prefer": prefer}),
        content=json.dumps(payload, ensure_ascii=False),
    )


def _looks_like_missing_workspace(status_code: int, body: str = "") -> bool:
    text = (body or "").lower()
    return status_code >= 400 and "workspace_id" in text


def _row_exists(table: str, wa_id: str, workspace_id: str = "") -> bool:
    wa_id = normalize_wa_id(wa_id)
    workspace_id = _resolve_workspace_id(workspace_id)
    if not table or not wa_id:
        return False

    urls = [
        f"{SUPABASE_URL}/rest/v1/{table}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}&select=wa_id&limit=1",
        f"{SUPABASE_URL}/rest/v1/{table}?wa_id=eq.{wa_id}&select=wa_id&limit=1",
    ]

    for url in urls:
        try:
            r = _get(url)
            if r.status_code == 200 and (r.json() or []):
                return True
        except Exception:
            continue

    return False


def sync_conversation_row(
    wa_id: str,
    text: str = "",
    created_at: str = "",
    workspace_id: str = "",
    name: str = "",
    telefone: str = "",
    extra: Optional[Dict[str, Any]] = None,
    handoff_pending: bool = False,
    handoff_active: bool = False,
    handoff_topic: Optional[str] = None,
) -> None:
    wa_id = normalize_wa_id(wa_id)
    telefone = normalize_wa_id(telefone) or wa_id
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return

    status = "open"
    if handoff_active:
        status = "handoff_active"
    elif handoff_pending:
        status = "handoff_pending"

    payload = {
        "wa_id": wa_id,
        "name": name or "",
        "telefone": telefone,
        "status": status,
        "handoff_pending": bool(handoff_pending),
        "handoff_active": bool(handoff_active),
        "handoff_topic": handoff_topic,
        "last_text": text or "",
        "last_at": created_at,
        "workspace_id": workspace_id or DEFAULT_WORKSPACE_ID,
    }
    extra = extra or {}
    for key in [
        "stage",
        "status",
        "source",
        "last_source",
        "campaign",
        "tags",
        "owner",
        "assigned_to",
        "human_owner",
        "closed_at",
        "lead_score",
        "lead_temperature",
        "lead_theme",
        "lead_stage",
        "priority",
        "flow_state",
        "flow_data",
        "entry_type",
        "inbound_type",
        "attendance_mode",
        "automation_paused",
        "bot_enabled",
        "company",
        "email",
        "segment",
        "segmento",
        "instagram",
        "site",
        "linkedin",
        "google_business",
        "service",
        "service_interest",
        "service_contracted",
        "responsavel",
        "cnpj",
        "publico_alvo",
        "diferenciais",
        "objetivos",
        "metricas",
        "tom_de_voz",
        "concorrentes",
        "referencias",
        "frequencia",
        "desafios",
        "orcamento",
        "prazo",
        "origem_lead",
        "fila",
        "automation_stage",
        "welcome_sent_at",
        "intelligence_sent_at",
        "internal_diagnosis_notified_at",
        "welcome_summary",
        "briefing_summary",
        "diagnosis_summary",
        "score_geral",
        "score_marketing",
        "score_vendas",
        "score_automacao",
        "score_dados",
        "score_relacionamento",
        "temperatura",
        "principal_oportunidade",
        "servico_mugo_recomendado",
        "resumo_gerado",
        "respostas_completas",
        "intelligence_received_at",
    ]:
        if key in extra and extra.get(key) is not None:
            payload[key] = extra.get(key)

    url = f"{SUPABASE_URL}/rest/v1/{CONVERSATIONS_TABLE}?on_conflict=workspace_id,wa_id"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{CONVERSATIONS_TABLE}?on_conflict=wa_id"

    try:
        resp = _post(url, payload, prefer="resolution=merge-duplicates,return=minimal")
        if resp.status_code not in (200, 201):
            legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}
            _post(legacy_url, legacy_payload, prefer="resolution=merge-duplicates,return=minimal")
        print("CONVERSATION_SYNC_OK:", wa_id)
    except Exception as e:
        print("CONVERSATION_SYNC_ERROR:", wa_id, str(e))


def _mirror_conversation_payload(payload: Dict[str, Any]) -> None:
    if not CONVERSATIONS_TABLE or CONVERSATIONS_TABLE == USERS_TABLE:
        return

    sync_conversation_row(
        wa_id=str(payload.get("wa_id") or "").strip(),
        text=str(payload.get("last_text") or payload.get("last_message") or ""),
        created_at=str(payload.get("last_at") or payload.get("updated_at") or ""),
        workspace_id=str(payload.get("workspace_id") or ""),
        name=str(payload.get("name") or ""),
        telefone=str(payload.get("telefone") or ""),
        extra=payload,
        handoff_pending=bool(payload.get("handoff_pending") or False),
        handoff_active=bool(payload.get("handoff_active") or False),
        handoff_topic=payload.get("handoff_topic"),
    )


def _build_message_only_conversation(
    wa_id: str,
    last: Dict[str, Any],
    totals_by: Dict[str, int],
    next_task_by: Dict[str, Dict[str, Any]],
    workspace_id: str = "",
) -> Dict[str, Any]:
    meta = last.get("meta") or {}
    return {
        "workspace_id": workspace_id,
        "wa_id": wa_id,
        "name": "",
        "telefone": wa_id,
        "stage": "Novo",
        "notes": "",
        "tags": [],
        "assigned_to": "",
        "source": meta.get("source") or "",
        "last_source": meta.get("source") or "",
        "campaign": meta.get("campaign") or "",
        "handoff_active": False,
        "handoff_topic": "",
        "first_message_sent": False,
        "updated_at": last.get("created_at") or "",
        "last_message": (last.get("text") or ""),
        "last_message_at": (last.get("created_at") or ""),
        "last_message_dir": (last.get("direction") or ""),
        "total_messages": totals_by.get(wa_id, 0),
        "lead_score": 0,
        "lead_temperature": "frio",
        "lead_theme": "indefinido",
        "lead_stage": "novo",
        "priority": 0,
        "entry_type": "",
        "inbound_type": "",
        "attendance_mode": "",
        "human_owner": "",
        "automation_paused": False,
        "bot_enabled": True,
        "qualified_at": "",
        "handoff_at": "",
        "closed_at": "",
        "next_task": next_task_by.get(wa_id),
    }


def upsert_user(wa_id: str, name: str = "", telefone: str = "", workspace_id: str = "", **extra) -> Dict[str, Any]:
    wa_id = normalize_wa_id(wa_id)
    telefone = normalize_wa_id(telefone)
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return {"wa_id": "", "workspace_id": workspace_id, "first_message_sent": False, "handoff_active": False}

    payload: Dict[str, Any] = {"wa_id": wa_id, "workspace_id": workspace_id}

    if name is not None and str(name).strip():
        payload["name"] = str(name).strip()

    if telefone:
        payload["telefone"] = telefone

    allowed_keys = [
        "first_message_sent",
        "handoff_active",
        "handoff_pending",
        "handoff_topic",
        "stage",
        "status",
        "notes",
        "tags",
        "owner",
        "assigned_to",
        "company",
        "email",
        "segment",
        "segmento",
        "instagram",
        "site",
        "linkedin",
        "google_business",
        "service",
        "service_interest",
        "service_contracted",
        "responsavel",
        "cnpj",
        "publico_alvo",
        "diferenciais",
        "objetivos",
        "metricas",
        "tom_de_voz",
        "concorrentes",
        "referencias",
        "frequencia",
        "desafios",
        "orcamento",
        "prazo",
        "origem_lead",
        "fila",
        "automation_stage",
        "welcome_sent_at",
        "intelligence_sent_at",
        "internal_diagnosis_notified_at",
        "welcome_summary",
        "briefing_summary",
        "diagnosis_summary",
        "score_geral",
        "score_marketing",
        "score_vendas",
        "score_automacao",
        "score_dados",
        "score_relacionamento",
        "temperatura",
        "principal_oportunidade",
        "servico_mugo_recomendado",
        "resumo_gerado",
        "respostas_completas",
        "intelligence_received_at",
        "source",
        "last_source",
        "campaign",
        "last_in_at",
        "last_out_at",
        "last_text",
        "last_at",
        "last_message",
        "updated_at",
        "lead_score",
        "lead_temperature",
        "lead_theme",
        "lead_stage",
        "priority",
        "flow_state",
        "flow_data",
        # base nova
        "entry_type",
        "inbound_type",
        "attendance_mode",
        "human_owner",
        "automation_paused",
        "bot_enabled",
        "qualified_at",
        "handoff_at",
        "closed_at",
    ]

    for k in allowed_keys:
        if k in extra and extra[k] is not None:
            payload[k] = extra[k]

    url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?on_conflict=workspace_id,wa_id"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?on_conflict=wa_id"
    existed_in_users = _row_exists(USERS_TABLE, wa_id, workspace_id=workspace_id)
    existed_in_conversations = _row_exists(CONVERSATIONS_TABLE, wa_id, workspace_id=workspace_id)
    is_new_panel_conversation = not existed_in_users and not existed_in_conversations

    try:
        r = _post(url, payload, prefer="resolution=merge-duplicates,return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}
            r = _post(legacy_url, legacy_payload, prefer="resolution=merge-duplicates,return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            if rows:
                row = rows[0] or {}
                row["tags"] = _normalize_tags(row.get("tags"))
                sync_conversation_row(
                    wa_id=wa_id,
                    text=row.get("last_text") or "",
                    created_at=row.get("last_at") or "",
                    workspace_id=workspace_id,
                    name=row.get("name") or "",
                    telefone=row.get("telefone") or "",
                    extra=row,
                    handoff_pending=row.get("handoff_pending") or False,
                    handoff_active=row.get("handoff_active") or False,
                    handoff_topic=row.get("handoff_topic"),
                )
                if is_new_panel_conversation:
                    print(
                        "NEW_PANEL_CONVERSATION:",
                        json.dumps(
                            {
                                "wa_id": wa_id,
                                "workspace_id": workspace_id,
                                "name": row.get("name") or payload.get("name") or "",
                                "telefone": row.get("telefone") or payload.get("telefone") or "",
                                "last_at": row.get("last_at") or payload.get("last_at") or "",
                            },
                            ensure_ascii=False,
                        ),
                    )
                return {
                    "wa_id": row.get("wa_id") or wa_id,
                    "workspace_id": row.get("workspace_id") or workspace_id,
                    "first_message_sent": bool(row.get("first_message_sent") or False),
                    "handoff_active": bool(row.get("handoff_active") or False),
                    **row,
                }
        return {"_error": r.text, **payload}
    except Exception as e:
        return {"_error": str(e), **payload}


def mark_first_message_sent(wa_id: str, workspace_id: str = ""):
    wa_id = (wa_id or "").strip()
    if not wa_id:
        return {"ok": False}
    upsert_user(wa_id, workspace_id=workspace_id, first_message_sent=True)
    return {"ok": True}


def set_stage(wa_id: str, stage: str, workspace_id: str = ""):
    stage = (stage or "").strip() or "Novo"
    return upsert_user(wa_id, workspace_id=workspace_id, stage=stage, lead_stage=stage.lower())


def set_notes(wa_id: str, notes: str, workspace_id: str = ""):
    return upsert_user(wa_id, workspace_id=workspace_id, notes=notes)


def set_tags(wa_id: str, tags: Any, workspace_id: str = ""):
    t = tags
    if isinstance(tags, (list, dict)):
        t = tags
    elif isinstance(tags, str):
        t = tags.strip()
    return upsert_user(wa_id, workspace_id=workspace_id, tags=t)


def set_handoff_pending(wa_id: str, pending: bool, workspace_id: str = ""):
    return upsert_user(wa_id, workspace_id=workspace_id, handoff_pending=bool(pending))


def set_handoff_topic(wa_id: str, topic: str, workspace_id: str = ""):
    return upsert_user(
        wa_id,
        workspace_id=workspace_id,
        handoff_topic=(topic or "").strip(),
        handoff_active=True,
        handoff_at=_now_iso(),
    )


def clear_handoff(wa_id: str, workspace_id: str = ""):
    return upsert_user(
        wa_id,
        workspace_id=workspace_id,
        handoff_active=False,
        handoff_pending=False,
        handoff_topic="",
    )


def pause_automation(wa_id: str, paused: bool = True, workspace_id: str = ""):
    payload = {"automation_paused": bool(paused)}
    if paused:
        payload["bot_enabled"] = False
    else:
        payload["bot_enabled"] = True
    return upsert_user(wa_id, workspace_id=workspace_id, **payload)


def set_attendance_mode(wa_id: str, mode: str, workspace_id: str = ""):
    mode = (mode or "").strip() or "bot"
    return upsert_user(wa_id, workspace_id=workspace_id, attendance_mode=mode)


def set_entry_type(wa_id: str, entry_type: str, workspace_id: str = ""):
    entry_type = (entry_type or "").strip() or "organic"
    return upsert_user(wa_id, workspace_id=workspace_id, entry_type=entry_type, inbound_type=entry_type)


def update_lead_intelligence(wa_id: str, score: int, temperature: str, theme: str, workspace_id: str = "") -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return {"ok": False, "detail": "missing wa_id"}

    score_i = int(score or 0)

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
    }

    payload = {k: v for k, v in payload.items() if v is not None}
    url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?wa_id=eq.{wa_id}"

    try:
        r = _patch(url, payload, prefer="return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            r = _patch(legacy_url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            item = (rows[0] if rows else payload)
            if isinstance(item, dict):
                item["tags"] = _normalize_tags(item.get("tags"))
            return {"ok": True, "item": item}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def log_message(
    wa_id: str,
    direction: str,
    text: str,
    meta: Optional[dict] = None,
    workspace_id: str = "",
) -> Dict[str, Any]:
    wa_id = normalize_wa_id(wa_id)
    workspace_id = _resolve_workspace_id(workspace_id)
    direction = (direction or "").strip()
    text = (text or "").strip()
    if not wa_id or not direction or not text:
        return {"ok": False}

    now = _now_iso()

    payload: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "wa_id": wa_id,
        "direction": direction,
        "text": text,
        "created_at": now,
    }

    if meta is not None:
        payload["meta"] = meta

    url = f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
    legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}

    try:
        r = _post(url, payload, prefer="return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            r = _post(url, legacy_payload, prefer="return=representation")
        ok = r.status_code in (200, 201)

        user_patch: Dict[str, Any] = {
            "last_text": text,
            "last_message": text,
            "last_at": now,
            "updated_at": now,
        }

        if direction == "in":
            user_patch["last_in_at"] = now
        elif direction == "out":
            user_patch["last_out_at"] = now

        try:
            source = ""
            campaign = ""
            if isinstance(meta, dict):
                source = (meta.get("source") or "").strip()
                campaign = (meta.get("campaign") or "").strip()

            if source:
                user_patch["last_source"] = source
                user_patch["source"] = source

            if campaign:
                user_patch["campaign"] = campaign

            upsert_user(wa_id, workspace_id=workspace_id, **user_patch)
        except Exception:
            pass

        sync_conversation_row(
            wa_id=wa_id,
            text=text,
            created_at=now,
            workspace_id=workspace_id,
        )

        if ok:
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_recent_messages(wa_id: str, limit: int = 40, workspace_id: str = "") -> List[Dict[str, Any]]:
    wa_id = normalize_wa_id(wa_id)
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return []

    limit = max(1, min(int(limit or 40), 100))
    fetch_limit = min(200, max(limit * 3, 60))
    select_fields = "id,workspace_id,wa_id,direction,text,created_at,meta"
    rows_by_key: Dict[str, Dict[str, Any]] = {}

    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
            f"?workspace_id=eq.{workspace_id}"
            f"&wa_id=eq.{wa_id}"
            f"&select={select_fields}"
            f"&order=created_at.desc"
            f"&limit={fetch_limit}"
        )
        r = _get(url)
        if _looks_like_missing_workspace(r.status_code, r.text):
            legacy_url = (
                f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
                f"?wa_id=eq.{wa_id}"
                f"&select={select_fields}"
                f"&order=created_at.desc"
                f"&limit={fetch_limit}"
            )
            r = _get(legacy_url)
            if r.status_code == 200:
                rows = r.json() or []
                rows.sort(
                    key=lambda row: (
                        str(row.get("created_at") or ""),
                        str(row.get("id") or ""),
                    )
                )
                return rows[-limit:]

        if r.status_code == 200:
            for row in (r.json() or []):
                meta = _safe_json(row.get("meta"), {})
                dedupe_key = (
                    str(row.get("id") or "").strip()
                    or str(meta.get("message_id") or "").strip()
                    or f"{row.get('wa_id') or ''}:{row.get('direction') or ''}:{row.get('created_at') or ''}:{row.get('text') or ''}"
                )
                rows_by_key[dedupe_key] = {
                    **row,
                    "meta": meta if isinstance(meta, dict) else {},
                }

            legacy_null_url = (
                f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
                f"?workspace_id=is.null"
                f"&wa_id=eq.{wa_id}"
                f"&select={select_fields}"
                f"&order=created_at.desc"
                f"&limit={fetch_limit}"
            )
            legacy_null = _get(legacy_null_url)
            if legacy_null.status_code == 200:
                for row in (legacy_null.json() or []):
                    meta = _safe_json(row.get("meta"), {})
                    dedupe_key = (
                        str(row.get("id") or "").strip()
                        or str(meta.get("message_id") or "").strip()
                        or f"{row.get('wa_id') or ''}:{row.get('direction') or ''}:{row.get('created_at') or ''}:{row.get('text') or ''}"
                    )
                    rows_by_key[dedupe_key] = {
                        **row,
                        "meta": meta if isinstance(meta, dict) else {},
                    }

            rows = list(rows_by_key.values())
            rows.sort(
                key=lambda row: (
                    str(row.get("created_at") or ""),
                    str((row.get("meta") or {}).get("message_id") or ""),
                    str(row.get("id") or ""),
                )
            )
            return rows[-limit:]
    except Exception:
        pass

    return []


def list_conversations(limit: int = 200, workspace_id: str = "") -> List[Dict[str, Any]]:
    limit = int(limit or 200)
    workspace_id = _resolve_workspace_id(workspace_id)

    users_rows: List[Dict[str, Any]] = []
    users_url_candidates = [
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&select=*&order=priority.desc,lead_score.desc,last_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&select=*&order=last_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&select=*&order=updated_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&select=*&order=created_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&select=*&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?select=*&order=priority.desc,lead_score.desc,last_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?select=*&order=last_at.desc.nullslast&limit={limit}",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?select=*&limit={limit}",
    ]
    conv_rows: List[Dict[str, Any]] = []
    conv_url_candidates = []
    if CONVERSATIONS_TABLE and CONVERSATIONS_TABLE != USERS_TABLE:
        conv_url_candidates = [
            f"{SUPABASE_URL}/rest/v1/{CONVERSATIONS_TABLE}?workspace_id=eq.{workspace_id}&select=*&order=last_at.desc.nullslast&limit={limit}",
            f"{SUPABASE_URL}/rest/v1/{CONVERSATIONS_TABLE}?select=*&order=last_at.desc.nullslast&limit={limit}",
            f"{SUPABASE_URL}/rest/v1/{CONVERSATIONS_TABLE}?select=*&limit={limit}",
        ]

    try:
        for uurl in users_url_candidates:
            ur = _get(uurl)
            if ur.status_code == 200:
                rows = ur.json() or []
                if rows:
                    users_by_wa_id: Dict[str, Dict[str, Any]] = {
                        (row.get("wa_id") or "").strip(): row for row in users_rows if (row.get("wa_id") or "").strip()
                    }
                    for row in rows:
                        wa_id = (row.get("wa_id") or "").strip()
                        if not wa_id:
                            continue
                        users_by_wa_id[wa_id] = _merge_non_empty(users_by_wa_id.get(wa_id) or {}, row)
                    users_rows = list(users_by_wa_id.values())
    except Exception:
        users_rows = []

    try:
        for curl in conv_url_candidates:
            cr = _get(curl)
            if cr.status_code == 200:
                rows = cr.json() or []
                if rows:
                    conv_by_wa_id: Dict[str, Dict[str, Any]] = {
                        (row.get("wa_id") or "").strip(): row for row in conv_rows if (row.get("wa_id") or "").strip()
                    }
                    for row in rows:
                        wa_id = (row.get("wa_id") or "").strip()
                        if not wa_id:
                            continue
                        conv_by_wa_id[wa_id] = _merge_non_empty(conv_by_wa_id.get(wa_id) or {}, row)
                    conv_rows = list(conv_by_wa_id.values())
    except Exception:
        conv_rows = []

    print(f"list_conversations:users total={len(users_rows)}")
    print(f"list_conversations:conversations total={len(conv_rows)}")

    last_by: Dict[str, Dict[str, Any]] = {}
    totals_by: Dict[str, int] = {}
    next_task_by: Dict[str, Dict[str, Any]] = {}

    try:
        msg_url = (
            f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
            f"?workspace_id=eq.{workspace_id}"
            f"&select=workspace_id,wa_id,text,created_at,direction,meta"
            f"&order=created_at.desc"
            f"&limit={min(3000, limit * 12)}"
        )
        mr = _get(msg_url)
        if _looks_like_missing_workspace(mr.status_code, mr.text):
            msg_url = (
                f"{SUPABASE_URL}/rest/v1/{MESSAGES_TABLE}"
                f"?select=wa_id,text,created_at,direction,meta"
                f"&order=created_at.desc"
                f"&limit={min(3000, limit * 12)}"
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

    print(f"list_conversations:messages total={len(last_by)}")

    try:
        task_url = (
            f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}"
            f"?workspace_id=eq.{workspace_id}"
            f"&select=*&status=eq.open&order=due_at.asc&limit={min(3000, limit * 8)}"
        )
        tr = _get(task_url)
        if _looks_like_missing_workspace(tr.status_code, tr.text):
            task_url = (
                f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}"
                f"?select=*&status=eq.open&order=due_at.asc&limit={min(3000, limit * 8)}"
            )
            tr = _get(task_url)
        if tr.status_code == 200:
            rows = tr.json() or []
            for t in rows:
                wid = (t.get("wa_id") or "").strip()
                if wid and wid not in next_task_by:
                    next_task_by[wid] = t
    except Exception:
        pass

    merged_base_by: Dict[str, Dict[str, Any]] = {}
    for row in conv_rows:
        wa_id = (row.get("wa_id") or "").strip()
        if wa_id:
            merged_base_by[wa_id] = _merge_non_empty(merged_base_by.get(wa_id) or {}, row)

    for row in users_rows:
        wa_id = (row.get("wa_id") or "").strip()
        if not wa_id:
            continue
        current = merged_base_by.get(wa_id) or {}
        merged_base_by[wa_id] = _merge_non_empty(current, row)

    base_rows = list(merged_base_by.values())

    if not base_rows:
        items: List[Dict[str, Any]] = []
        for wa_id, last in last_by.items():
            item = _build_message_only_conversation(wa_id, last, totals_by, next_task_by, workspace_id=workspace_id)
            _mirror_conversation_payload({
                "workspace_id": workspace_id,
                "wa_id": wa_id,
                "telefone": "",
                "stage": item["stage"],
                "lead_stage": item["lead_stage"],
                "last_text": item["last_message"],
                "last_message": item["last_message"],
                "last_at": item["last_message_at"],
                "source": item["source"],
                "last_source": item["last_source"],
                "campaign": item["campaign"],
                "attendance_mode": item["attendance_mode"],
                "automation_paused": item["automation_paused"],
                "bot_enabled": item["bot_enabled"],
            })
            print("DERIVED_PANEL_CONVERSATION:", json.dumps({"wa_id": wa_id, "workspace_id": workspace_id}, ensure_ascii=False))
            items.append(item)

        items.sort(key=lambda x: x.get("last_message_at") or "", reverse=True)
        print(f"list_conversations:final total={len(items)}")
        return items[:limit]

    items: List[Dict[str, Any]] = []
    for u in base_rows:
        wa_id = (u.get("wa_id") or "").strip()
        if not wa_id:
            continue

        last = last_by.get(wa_id) or {}
        last_meta = last.get("meta") or {}

        items.append({
            "workspace_id": u.get("workspace_id") or workspace_id,
            "wa_id": wa_id,
            "name": u.get("name") or "",
            "telefone": u.get("telefone") or "",
            "company": u.get("company") or "",
            "email": u.get("email") or "",
            "segment": u.get("segment") or "",
            "segmento": u.get("segmento") or "",
            "instagram": u.get("instagram") or "",
            "site": u.get("site") or "",
            "linkedin": u.get("linkedin") or "",
            "google_business": u.get("google_business") or "",
            "service": u.get("service") or "",
            "service_interest": u.get("service_interest") or "",
            "service_contracted": u.get("service_contracted") or "",
            "responsavel": u.get("responsavel") or "",
            "cnpj": u.get("cnpj") or "",
            "publico_alvo": u.get("publico_alvo") or "",
            "diferenciais": u.get("diferenciais") or "",
            "objetivos": u.get("objetivos") or "",
            "metricas": u.get("metricas") or "",
            "tom_de_voz": u.get("tom_de_voz") or "",
            "concorrentes": u.get("concorrentes") or "",
            "referencias": u.get("referencias") or "",
            "frequencia": u.get("frequencia") or "",
            "desafios": u.get("desafios") or "",
            "orcamento": u.get("orcamento") or "",
            "prazo": u.get("prazo") or "",
            "origem_lead": u.get("origem_lead") or "",
            "fila": u.get("fila") or "",
            "automation_stage": u.get("automation_stage") or "",
            "welcome_sent_at": u.get("welcome_sent_at") or "",
            "intelligence_sent_at": u.get("intelligence_sent_at") or "",
            "internal_diagnosis_notified_at": u.get("internal_diagnosis_notified_at") or "",
            "welcome_summary": _safe_json(u.get("welcome_summary"), {}),
            "briefing_summary": _safe_json(u.get("briefing_summary"), {}),
            "diagnosis_summary": _safe_json(u.get("diagnosis_summary"), {}),
            "score_geral": u.get("score_geral") or "",
            "score_marketing": u.get("score_marketing") or "",
            "score_vendas": u.get("score_vendas") or "",
            "score_automacao": u.get("score_automacao") or "",
            "score_dados": u.get("score_dados") or "",
            "score_relacionamento": u.get("score_relacionamento") or "",
            "temperatura": u.get("temperatura") or "",
            "principal_oportunidade": u.get("principal_oportunidade") or "",
            "servico_mugo_recomendado": u.get("servico_mugo_recomendado") or "",
            "resumo_gerado": u.get("resumo_gerado") or "",
            "respostas_completas": _safe_json(u.get("respostas_completas"), {}),
            "intelligence_received_at": u.get("intelligence_received_at") or "",
            "stage": u.get("stage") or "Novo",
            "notes": u.get("notes") or "",
            "tags": _normalize_tags(u.get("tags")),
            "assigned_to": u.get("assigned_to") or u.get("owner") or "",
            "source": u.get("source") or last_meta.get("source") or "",
            "last_source": u.get("last_source") or last_meta.get("source") or "",
            "campaign": u.get("campaign") or last_meta.get("campaign") or "",
            "handoff_active": bool(u.get("handoff_active") or False),
            "handoff_topic": u.get("handoff_topic") or "",
            "first_message_sent": bool(u.get("first_message_sent") or False),
            "created_at": u.get("created_at") or (last.get("created_at") or ""),
            "last_at": u.get("last_at") or (last.get("created_at") or ""),
            "updated_at": u.get("last_at") or u.get("updated_at") or u.get("created_at") or "",
            "last_message": (last.get("text") or (u.get("last_text") or u.get("last_message") or "")),
            "last_message_at": (last.get("created_at") or (u.get("last_at") or "")),
            "last_message_dir": (last.get("direction") or ""),
            "total_messages": totals_by.get(wa_id, 0),
            "lead_score": u.get("lead_score") or 0,
            "lead_temperature": u.get("lead_temperature") or "frio",
            "lead_theme": u.get("lead_theme") or "indefinido",
            "lead_stage": u.get("lead_stage") or "novo",
            "priority": u.get("priority") or 0,
            "entry_type": u.get("entry_type") or "",
            "inbound_type": u.get("inbound_type") or "",
            "attendance_mode": u.get("attendance_mode") or "",
            "flow_state": u.get("flow_state") or "",
            "flow_data": _safe_json(u.get("flow_data"), {}),
            "human_owner": u.get("human_owner") or "",
            "automation_paused": bool(u.get("automation_paused") or False),
            "bot_enabled": bool(u.get("bot_enabled") if u.get("bot_enabled") is not None else True),
            "qualified_at": u.get("qualified_at") or "",
            "handoff_at": u.get("handoff_at") or "",
            "closed_at": u.get("closed_at") or "",
            "next_task": next_task_by.get(wa_id),
        })

    known_ids = {str(item.get("wa_id") or "").strip() for item in items if item.get("wa_id")}
    for wa_id, last in last_by.items():
        if not wa_id or wa_id in known_ids:
            continue

        item = _build_message_only_conversation(wa_id, last, totals_by, next_task_by, workspace_id=workspace_id)
        _mirror_conversation_payload({
            "workspace_id": workspace_id,
            "wa_id": wa_id,
            "telefone": "",
            "stage": item["stage"],
            "lead_stage": item["lead_stage"],
            "last_text": item["last_message"],
            "last_message": item["last_message"],
            "last_at": item["last_message_at"],
            "source": item["source"],
            "last_source": item["last_source"],
            "campaign": item["campaign"],
            "attendance_mode": item["attendance_mode"],
            "automation_paused": item["automation_paused"],
            "bot_enabled": item["bot_enabled"],
        })
        print("DERIVED_PANEL_CONVERSATION:", json.dumps({"wa_id": wa_id, "workspace_id": workspace_id}, ensure_ascii=False))
        items.append(item)

    items.sort(
        key=lambda x: (
            x.get("last_message_at") or "",
            x.get("last_at") or "",
            x.get("updated_at") or "",
            x.get("created_at") or "",
        ),
        reverse=True,
    )
    print(f"list_conversations:final total={len(items)}")
    return items[:limit]


def create_task(wa_id: str, title: str, due_at_iso: str, workspace_id: str = "") -> Dict[str, Any]:
    wa_id = normalize_wa_id(wa_id)
    title = (title or "").strip()
    due_at_iso = (due_at_iso or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)

    payload = {
        "workspace_id": workspace_id,
        "wa_id": wa_id,
        "title": title,
        "due_at": due_at_iso,
        "status": "open",
        "created_at": _now_iso(),
    }
    url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}"
    legacy_payload = {k: v for k, v in payload.items() if k != "workspace_id"}
    try:
        r = _post(url, payload, prefer="return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            r = _post(url, legacy_payload, prefer="return=representation")
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
    limit: int = 200,
    workspace_id: str = "",
) -> List[Dict[str, Any]]:
    workspace_id = _resolve_workspace_id(workspace_id)
    filters = ["select=*", "order=due_at.asc", f"limit={int(limit)}", f"workspace_id=eq.{workspace_id}"]
    if status:
        filters.append(f"status=eq.{status}")
    if wa_id:
        filters.append(f"wa_id=eq.{wa_id}")
    if due_before:
        filters.append(f"due_at=lt.{due_before}")
    url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?" + "&".join(filters)
    try:
        r = _get(url)
        if _looks_like_missing_workspace(r.status_code, r.text):
            legacy_filters = [f for f in filters if not f.startswith("workspace_id=")]
            r = _get(f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?" + "&".join(legacy_filters))
        if r.status_code == 200:
            return r.json() or []
    except Exception:
        pass
    return []


def done_task(task_id: str, workspace_id: str = "") -> Dict[str, Any]:
    task_id = (task_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not task_id:
        return {"ok": False, "detail": "missing id"}

    url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?workspace_id=eq.{workspace_id}&id=eq.{task_id}"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?id=eq.{task_id}"
    payload = {
        "status": "done",
        "done_at": _now_iso(),
    }
    try:
        r = _patch(url, payload, prefer="return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            r = _patch(legacy_url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_task(task_id: str, workspace_id: str = "", **fields) -> Dict[str, Any]:
    task_id = (task_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not task_id:
        return {"ok": False, "detail": "missing id"}

    payload: Dict[str, Any] = {}
    for k in ("due_at", "title", "status", "wa_id"):
        if k in fields and fields[k] is not None:
            payload[k] = fields[k]

    if not payload:
        return {"ok": False, "detail": "no fields to update"}

    url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?workspace_id=eq.{workspace_id}&id=eq.{task_id}"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{TASKS_TABLE}?id=eq.{task_id}"
    try:
        r = _patch(url, payload, prefer="return=representation")
        if _looks_like_missing_workspace(r.status_code, r.text):
            r = _patch(legacy_url, payload, prefer="return=representation")
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_flow(wa_id: str, workspace_id: str = "") -> Dict[str, Any]:
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return {"state": None, "data": {}}

    url = f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}&select=flow_state,flow_data"
    fallback_urls = [
        f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?wa_id=eq.{wa_id}&select=flow_state,flow_data",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}&select=flow_state,flow_data",
        f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?wa_id=eq.{wa_id}&select=flow_state,flow_data",
    ]
    try:
        r = _get(url)
        if r.status_code != 200:
            for fallback_url in fallback_urls:
                r = _get(fallback_url)
                if r.status_code == 200:
                    break
        if r.status_code == 200:
            rows = r.json() or []
            if rows:
                row = rows[0] or {}
                return {
                    "state": row.get("flow_state"),
                    "data": _safe_json(row.get("flow_data"), {}),
                }
    except Exception:
        pass

    return {"state": None, "data": {}}


def set_flow_state(wa_id: str, state: Optional[str], workspace_id: str = ""):
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return {"ok": False}

    url = f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?wa_id=eq.{wa_id}"
    fallback_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    fallback_legacy_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?wa_id=eq.{wa_id}"
    payload = {"flow_state": state}

    try:
        r = _patch(url, payload, prefer="return=representation")
        if r.status_code >= 400:
            for next_url in (legacy_url, fallback_url, fallback_legacy_url):
                r = _patch(next_url, payload, prefer="return=representation")
                if r.status_code in (200, 201, 204):
                    break
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def merge_flow_data(wa_id: str, patch: Dict[str, Any], workspace_id: str = ""):
    flow = get_flow(wa_id, workspace_id=workspace_id)
    data = flow.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    if patch and isinstance(patch, dict):
        data.update(patch)
    return upsert_user(wa_id, workspace_id=workspace_id, flow_data=data)


def clear_flow(wa_id: str, workspace_id: str = ""):
    wa_id = (wa_id or "").strip()
    workspace_id = _resolve_workspace_id(workspace_id)
    if not wa_id:
        return {"ok": False}

    url = f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    legacy_url = f"{SUPABASE_URL}/rest/v1/{FLOW_TABLE}?wa_id=eq.{wa_id}"
    fallback_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?workspace_id=eq.{workspace_id}&wa_id=eq.{wa_id}"
    fallback_legacy_url = f"{SUPABASE_URL}/rest/v1/{USERS_TABLE}?wa_id=eq.{wa_id}"
    payload = {"flow_state": None, "flow_data": {}}

    try:
        r = _patch(url, payload, prefer="return=representation")
        if r.status_code >= 400:
            for next_url in (legacy_url, fallback_url, fallback_legacy_url):
                r = _patch(next_url, payload, prefer="return=representation")
                if r.status_code in (200, 201, 204):
                    break
        if r.status_code in (200, 201):
            rows = r.json() or []
            return {"ok": True, "item": (rows[0] if rows else payload)}
        if r.status_code == 204:
            return {"ok": True, "item": payload}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}
