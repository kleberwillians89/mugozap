import os
import re
import requests
from typing import Any, Dict, List, Union, Optional

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


# ============================================================
# Builders (Cloud API)
# ============================================================
def _build_text_payload(to_wa_id: str, text: str) -> Dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text.strip()[:4096]},
    }


def _clip_button_title(title: str) -> str:
    # Cloud API: botão "reply.title" ~ até 20 chars (senão falha)
    t = (title or "").strip()
    return t[:20] if len(t) > 20 else t


def _build_buttons_payload(to_wa_id: str, text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    # Cloud API: máximo 3 botões por mensagem
    safe_buttons = []
    for b in (buttons or [])[:3]:
        bid = (b.get("id") or "").strip()[:256]
        ttl = _clip_button_title(b.get("title") or "")
        if not bid or not ttl:
            continue
        safe_buttons.append({"type": "reply", "reply": {"id": bid, "title": ttl}})

    if not safe_buttons:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": (text or "").strip()[:1024]},
            "action": {"buttons": safe_buttons},
        },
    }


def _clip_list_button_text(s: str) -> str:
    # Texto do botão que abre a lista (ex.: "Selecionar") ~ até 20 chars
    t = (s or "").strip()
    return t[:20] if len(t) > 20 else t


def _clip_list_section_title(s: str) -> str:
    # Título da seção ~ até 24 chars
    t = (s or "").strip()
    return t[:24] if len(t) > 24 else t


def _clip_list_row_title(s: str) -> str:
    # Título de cada opção ~ até 24 chars
    t = (s or "").strip()
    return t[:24] if len(t) > 24 else t


def _clip_list_row_desc(s: str) -> str:
    # Descrição opcional ~ até 72 chars (bom pra UX)
    t = (s or "").strip()
    return t[:72] if len(t) > 72 else t


def _build_list_payload(
    to_wa_id: str,
    text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    sections = [
      {
        "title": "Serviços",
        "rows": [
          {"id":"SVC_AUTOMACAO","title":"Automação","description":"Atendimento, CRM, processos"},
          ...
        ]
      }
    ]
    """
    safe_sections: List[Dict[str, Any]] = []

    for s in (sections or [])[:10]:  # Cloud API: normalmente até 10 seções
        stitle = _clip_list_section_title(s.get("title") or "Opções")
        rows_in = s.get("rows") or []
        safe_rows = []

        for r in rows_in[:10]:  # Cloud API: até 10 rows por seção
            rid = (r.get("id") or "").strip()[:256]
            rtitle = _clip_list_row_title(r.get("title") or "")
            rdesc = _clip_list_row_desc(r.get("description") or "")
            if not rid or not rtitle:
                continue
            row_obj: Dict[str, Any] = {"id": rid, "title": rtitle}
            if rdesc:
                row_obj["description"] = rdesc
            safe_rows.append(row_obj)

        if safe_rows:
            safe_sections.append({"title": stitle, "rows": safe_rows})

    if not safe_sections:
        return _build_text_payload(to_wa_id, text)

    return {
        "messaging_product": "whatsapp",
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


# ============================================================
# Public API
# ============================================================
def send_message(to_wa_id: str, payload: Union[str, Dict[str, Any]]):
    """
    Aceita:
      - string: envia mensagem de texto simples

      - dict (compatível com teu app.py/safe_send):
          {"type":"text","text":"..."}
          {"type":"buttons","text":"...","buttons":[{id,title}]}
          {"type":"list","text":"...","button":"Selecionar","sections":[{title,rows:[{id,title,description}]}]}
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

    # ------------------------------------------------------------
    # payload string => text
    # ------------------------------------------------------------
    if isinstance(payload, str):
        if not payload.strip():
            raise RuntimeError("Texto vazio")
        body = _build_text_payload(to_wa_id, payload)

    # ------------------------------------------------------------
    # payload dict
    # ------------------------------------------------------------
    elif isinstance(payload, dict):
        ptype = (payload.get("type") or "").strip().lower()

        # buttons
        if ptype == "buttons":
            text = (payload.get("text") or "").strip()
            buttons = payload.get("buttons") or []
            if not text or not isinstance(buttons, list) or not buttons:
                raise RuntimeError("Payload buttons inválido")
            body = _build_buttons_payload(to_wa_id, text, buttons)

        # list (novo)
        elif ptype == "list":
            text = (payload.get("text") or "").strip()
            button_text = (payload.get("button") or "Selecionar").strip()
            sections = payload.get("sections") or []
            if not text or not isinstance(sections, list) or not sections:
                raise RuntimeError("Payload list inválido")
            body = _build_list_payload(to_wa_id, text, button_text, sections)

        # text default
        else:
            text = (payload.get("text") or "").strip()
            if not text:
                raise RuntimeError("Texto vazio")
            body = _build_text_payload(to_wa_id, text)

    else:
        raise RuntimeError("Payload inválido: esperado str ou dict")

    # ------------------------------------------------------------
    # send
    # ------------------------------------------------------------
    try:
        r = requests.post(url, json=body, headers=headers, timeout=20)
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de conexão com Meta: {e}")

    if r.status_code >= 300:
        # IMPORTANTÍSSIMO: isso te diz EXATAMENTE o motivo do botão/lista não aparecer
        raise RuntimeError(f"WA send error {r.status_code}: {r.text}")

    return r.json()