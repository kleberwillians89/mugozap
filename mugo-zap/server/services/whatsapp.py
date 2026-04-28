import os
import re
import json
from typing import Any, Dict, List, Union

import requests


def _clean_number(n: str) -> str:
    return re.sub(r"\D+", "", n or "")


WHATSAPP_TOKEN = (
    os.getenv("WHATSAPP_TOKEN")
    or os.getenv("WA_TOKEN")
    or os.getenv("META_WHATSAPP_TOKEN")
    or ""
).strip()

PHONE_NUMBER_ID = (
    os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    or os.getenv("PHONE_NUMBER_ID")
    or os.getenv("WA_PHONE_NUMBER_ID")
    or ""
).strip()

GRAPH_API_VERSION = (os.getenv("WHATSAPP_GRAPH_VERSION") or "v20.0").strip()
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"


def _short(value: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
    except Exception:
        text = str(value or "")
    if WHATSAPP_TOKEN:
        text = text.replace(WHATSAPP_TOKEN, "[redacted]")
    return text[:limit]


def _payload_stats(body: Dict[str, Any]) -> Dict[str, Any]:
    ptype = (body.get("type") or "").strip()
    stats: Dict[str, Any] = {"type": ptype}

    if ptype == "text":
        stats["text_len"] = len(((body.get("text") or {}).get("body") or ""))
    elif ptype == "interactive":
        inter = body.get("interactive") or {}
        itype = (inter.get("type") or "").strip()
        stats["interactive_type"] = itype
        body_text = ((inter.get("body") or {}).get("text") or "")
        stats["text_len"] = len(body_text)
        action = inter.get("action") or {}
        if itype == "button":
            stats["buttons"] = len(action.get("buttons") or [])
        if itype == "list":
            stats["sections"] = len(action.get("sections") or [])
            stats["rows"] = sum(len((section or {}).get("rows") or []) for section in action.get("sections") or [])

    return stats


def meta_env_status() -> Dict[str, Any]:
    verify_token = (
        os.getenv("WHATSAPP_VERIFY_TOKEN")
        or os.getenv("VERIFY_TOKEN")
        or ""
    ).strip()
    return {
        "whatsapp_token_present": bool(WHATSAPP_TOKEN),
        "whatsapp_phone_number_id": PHONE_NUMBER_ID or "",
        "whatsapp_verify_token_present": bool(verify_token),
        "meta_app_secret_present": bool((os.getenv("META_APP_SECRET") or "").strip()),
    }


def _build_text_payload(to_wa_id: str, text: str) -> Dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text.strip()[:4096],
        },
    }


def _clip_button_title(title: str) -> str:
    t = (title or "").strip()
    return t[:20] if len(t) > 20 else t


def _build_buttons_payload(to_wa_id: str, text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    safe_buttons = []
    for b in (buttons or [])[:3]:
        bid = (b.get("id") or "").strip()[:256]
        ttl = _clip_button_title(b.get("title") or "")
        if not bid or not ttl:
            continue
        safe_buttons.append(
            {
                "type": "reply",
                "reply": {
                    "id": bid,
                    "title": ttl,
                },
            }
        )

    if not safe_buttons:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": (text or "").strip()[:1024]},
            "action": {"buttons": safe_buttons},
        },
    }


def _clip_list_button_text(s: str) -> str:
    t = (s or "").strip()
    return t[:20] if len(t) > 20 else t


def _clip_list_section_title(s: str) -> str:
    t = (s or "").strip()
    return t[:24] if len(t) > 24 else t


def _clip_list_row_title(s: str) -> str:
    t = (s or "").strip()
    return t[:24] if len(t) > 24 else t


def _clip_list_row_desc(s: str) -> str:
    t = (s or "").strip()
    return t[:72] if len(t) > 72 else t


def _build_list_payload(
    to_wa_id: str,
    text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    safe_sections: List[Dict[str, Any]] = []

    for s in (sections or [])[:10]:
        stitle = _clip_list_section_title(s.get("title") or "Opções")
        rows_in = s.get("rows") or []
        safe_rows = []

        for r in rows_in[:10]:
            rid = (r.get("id") or "").strip()[:256]
            rtitle = _clip_list_row_title(r.get("title") or "")
            rdesc = _clip_list_row_desc(r.get("description") or "")
            if not rid or not rtitle:
                continue

            row_obj: Dict[str, Any] = {
                "id": rid,
                "title": rtitle,
            }
            if rdesc:
                row_obj["description"] = rdesc

            safe_rows.append(row_obj)

        if safe_rows:
            safe_sections.append(
                {
                    "title": stitle,
                    "rows": safe_rows,
                }
            )

    if not safe_sections:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": (text or "").strip()[:1024]},
            "action": {
                "button": _clip_list_button_text(button_text or "Selecionar"),
                "sections": safe_sections,
            },
        },
    }


def _normalize_payload(to_wa_id: str, payload: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(payload, str):
        if not payload.strip():
            raise RuntimeError("Texto vazio")
        return _build_text_payload(to_wa_id, payload)

    if not isinstance(payload, dict):
        raise RuntimeError("Payload inválido: esperado str ou dict")

    ptype = (payload.get("type") or "").strip().lower()

    if ptype == "buttons":
        text = (payload.get("text") or "").strip()
        buttons = payload.get("buttons") or []
        if not text or not isinstance(buttons, list) or not buttons:
            raise RuntimeError("Payload buttons inválido")
        return _build_buttons_payload(to_wa_id, text, buttons)

    if ptype == "list":
        text = (payload.get("text") or "").strip()
        button_text = (payload.get("button") or "Selecionar").strip()
        sections = payload.get("sections") or []
        if not text or not isinstance(sections, list) or not sections:
            raise RuntimeError("Payload list inválido")
        return _build_list_payload(to_wa_id, text, button_text, sections)

    text = (payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("Texto vazio")
    return _build_text_payload(to_wa_id, text)


def send_message_detailed(to_wa_id: str, payload: Union[str, Dict[str, Any]], *, raise_for_status: bool = True) -> Dict[str, Any]:
    to_wa_id = _clean_number(to_wa_id)

    if not WHATSAPP_TOKEN:
        raise RuntimeError("ENV faltando: WHATSAPP_TOKEN")
    if not PHONE_NUMBER_ID:
        raise RuntimeError("ENV faltando: WHATSAPP_PHONE_NUMBER_ID")
    if not to_wa_id:
        raise RuntimeError("Número de destino inválido")

    body = _normalize_payload(to_wa_id, payload)
    stats = _payload_stats(body)
    print(
        "WHATSAPP_SEND_ATTEMPT "
        f"wa_id={to_wa_id} message_type={stats.get('type')} phone_number_id={PHONE_NUMBER_ID or 'missing'} stats={stats}"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(BASE_URL, json=body, headers=headers, timeout=20)
    except requests.RequestException as e:
        print(
            "WHATSAPP_SEND_ERROR "
            f"wa_id={to_wa_id} error_type={type(e).__name__} message={str(e)[:500]}"
        )
        raise RuntimeError(f"Erro de conexão com Meta: {e}")

    body_preview = _short(r.text)
    print(
        "WHATSAPP_SEND_RESULT "
        f"wa_id={to_wa_id} status_code={r.status_code} body={body_preview}"
    )

    if r.status_code >= 300:
        print(
            "WHATSAPP_SEND_ERROR "
            f"wa_id={to_wa_id} error_type=HTTPStatusError message=status_code={r.status_code} body={body_preview}"
        )
        if raise_for_status:
            raise RuntimeError(f"WA send error {r.status_code}: {r.text}")

    try:
        parsed = r.json()
    except Exception:
        parsed = {"raw": r.text}

    return {
        "ok": r.status_code < 300,
        "status_code": r.status_code,
        "body": _short(parsed),
        "raw_body": parsed,
        "phone_number_id": PHONE_NUMBER_ID,
    }


def send_message(to_wa_id: str, payload: Union[str, Dict[str, Any]]):
    return send_message_detailed(to_wa_id, payload).get("raw_body") or {"ok": True}
