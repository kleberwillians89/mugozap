import os
import re
import requests

def _clean_number(n: str) -> str:
    return re.sub(r"\D+", "", n or "")

# aceita múltiplos nomes de env (evita erro besta de nome diferente)
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


def send_message(to_wa_id: str, text: str):
    to_wa_id = _clean_number(to_wa_id)

    if not WHATSAPP_TOKEN:
        raise RuntimeError("ENV faltando: WHATSAPP_TOKEN")

    if not PHONE_NUMBER_ID:
        raise RuntimeError("ENV faltando: WHATSAPP_PHONE_NUMBER_ID")

    if not to_wa_id:
        raise RuntimeError("Número de destino inválido")

    if not text or not text.strip():
        raise RuntimeError("Texto vazio")

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text.strip()},
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de conexão com Meta: {e}")

    if r.status_code >= 300:
        raise RuntimeError(
            f"WA send error {r.status_code}: {r.text}"
        )

    return r.json()
