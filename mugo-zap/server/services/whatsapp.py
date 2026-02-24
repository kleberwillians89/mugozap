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

def _build_text_payload(to_wa_id: str, text: str) -> Dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text.strip()},
    }

def _build_buttons_payload(to_wa_id: str, text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    # WhatsApp Cloud: máximo 3 botões por mensagem
    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons[:3]
                ]
            },
        },
    }

def send_message(to_wa_id: str, payload: Union[str, Dict[str, Any]]):
    """
    Aceita:
      - string: envia mensagem de texto simples
      - dict: {"type":"text","text":"..."} ou {"type":"buttons","text":"...","buttons":[{id,title}]}
    """
    to_wa_id = _clean_number(to_wa_id)

    if not WHATSAPP_TOKEN:
        raise RuntimeError("ENV faltando: WHATSAPP_TOKEN")
    if not PHONE_NUMBER_ID:
        raise RuntimeError("ENV faltando: WHATSAPP_PHONE_NUMBER_ID")
    if not to_wa_id:
        raise RuntimeError("Número de destino inválido")

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    if isinstance(payload, str):
        if not payload.strip():
            raise RuntimeError("Texto vazio")
        body = _build_text_payload(to_wa_id, payload)

    elif isinstance(payload, dict):
        ptype = (payload.get("type") or "").strip().lower()

        if ptype == "buttons":
            text = (payload.get("text") or "").strip()
            buttons = payload.get("buttons") or []
            if not text or not isinstance(buttons, list) or not buttons:
                raise RuntimeError("Payload buttons inválido")
            body = _build_buttons_payload(to_wa_id, text, buttons)

        else:
            text = (payload.get("text") or "").strip()
            if not text:
                raise RuntimeError("Texto vazio")
            body = _build_text_payload(to_wa_id, text)

    else:
        raise RuntimeError("Payload inválido: esperado str ou dict")

    try:
        r = requests.post(url, json=body, headers=headers, timeout=20)
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de conexão com Meta: {e}")

    if r.status_code >= 300:
        raise RuntimeError(f"WA send error {r.status_code}: {r.text}")

    return r.json()