# mugo-zap/server/services/whatsapp.py
import os
import re
import requests
from typing import Any, Dict, List, Union

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

GRAPH_VERSION = (os.getenv("WHATSAPP_GRAPH_VERSION") or "v20.0").strip()

def _build_text_payload(to_wa_id: str, text: str) -> Dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text.strip()},
    }

def _build_buttons_payload(to_wa_id: str, text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    # WhatsApp Cloud: máximo 3 botões por mensagem
    btns = []
    for b in (buttons or [])[:3]:
        bid = (b.get("id") or "").strip()
        title = (b.get("title") or "").strip()
        if bid and title:
            btns.append({"type": "reply", "reply": {"id": bid, "title": title}})

    if not btns:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": btns},
        },
    }

def _build_list_payload(
    to_wa_id: str,
    text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # list é ótima pra > 3 opções
    safe_sections = []
    for s in (sections or [])[:10]:
        title = (s.get("title") or "").strip()
        rows = s.get("rows") or []
        safe_rows = []
        for r in rows[:10]:
            rid = (r.get("id") or "").strip()
            rtitle = (r.get("title") or "").strip()
            desc = (r.get("description") or "").strip()
            if rid and rtitle:
                row = {"id": rid, "title": rtitle}
                if desc:
                    row["description"] = desc[:72]
                safe_rows.append(row)

        if title and safe_rows:
            safe_sections.append({"title": title[:24], "rows": safe_rows})

    if not safe_sections:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text},
            "action": {
                "button": (button_text or "Ver opções")[:20],
                "sections": safe_sections,
            },
        },
    }

def send_message(to_wa_id: str, payload: Union[str, Dict[str, Any]]):
    """
    Aceita:
      - string -> texto simples
      - dict -> {"type":"text"} | {"type":"buttons"} | {"type":"list"}
    """
    to_wa_id = _clean_number(to_wa_id)

    if not WHATSAPP_TOKEN:
        raise RuntimeError("ENV faltando: WHATSAPP_TOKEN")
    if not PHONE_NUMBER_ID:
        raise RuntimeError("ENV faltando: WHATSAPP_PHONE_NUMBER_ID")
    if not to_wa_id:
        raise RuntimeError("Número de destino inválido")

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            raise RuntimeError("Texto vazio")
        body = _build_text_payload(to_wa_id, text)

    elif isinstance(payload, dict):
        ptype = (payload.get("type") or "").strip().lower()

        if ptype == "buttons":
            text = (payload.get("text") or "").strip()
            buttons = payload.get("buttons") or []
            body = _build_buttons_payload(to_wa_id, text, buttons)

        elif ptype == "list":
            text = (payload.get("text") or "").strip()
            button_text = (payload.get("button_text") or "Ver opções").strip()
            sections = payload.get("sections") or []
            body = _build_list_payload(to_wa_id, text, button_text, sections)

        else:
            text = (payload.get("text") or "").strip()
            if not text:
                raise RuntimeError("Texto vazio")
            body = _build_text_payload(to_wa_id, text)

    else:
        raise RuntimeError("Payload inválido: esperado str ou dict")

    try:
        r = requests.post(url, json=body, headers=headers, timeout=18)
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de conexão com Meta: {e}")

    if r.status_code >= 300:
        raise RuntimeError(f"WA send error {r.status_code}: {r.text}")

    return r.json()