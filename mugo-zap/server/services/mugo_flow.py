# mugo-zap/server/services/mugo_flow.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

import httpx

# ============================================================
# ENV
# ============================================================
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

WA_FLOW_TABLE = (os.getenv("WA_FLOW_TABLE") or "whatsapp_flow_state").strip()

HTTP_TIMEOUT = float(os.getenv("FLOW_HTTP_TIMEOUT") or "10")
DEBUG_FLOW = (os.getenv("DEBUG_FLOW") or "").strip().lower() in ("1", "true", "yes")


# ============================================================
# DB helpers (Supabase REST)
# ============================================================
def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _flow_get(wa_id: str) -> Tuple[str, Dict[str, Any]]:
    """
    Retorna (state, data). Se não existir, retorna ("mugo_cta", {}).
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not wa_id:
        return "mugo_cta", {}

    url = f"{SUPABASE_URL}/rest/v1/{WA_FLOW_TABLE}"
    params = {
        "select": "state,data",
        "wa_id": f"eq.{wa_id}",
        "limit": "1",
    }

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            r = client.get(url, headers=_headers(), params=params)

        if r.status_code >= 300:
            return "mugo_cta", {}

        rows = r.json() or []
        if not rows:
            return "mugo_cta", {}

        row = rows[0] or {}
        state = (row.get("state") or "mugo_cta").strip() or "mugo_cta"
        data = row.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        return state, data

    except Exception:
        return "mugo_cta", {}


def _flow_save(wa_id: str, state: str, data: Dict[str, Any]) -> None:
    """
    Upsert (wa_id, state, data, updated_at)
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not wa_id:
        return

    payload = {
        "wa_id": wa_id,
        "state": (state or "mugo_cta").strip(),
        "data": data or {},
        "updated_at": _now_iso(),
    }

    url = f"{SUPABASE_URL}/rest/v1/{WA_FLOW_TABLE}?on_conflict=wa_id"
    headers = _headers()
    headers["Prefer"] = "resolution=merge-duplicates"

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            client.post(url, headers=headers, json=payload)
    except Exception:
        return


# ============================================================
# WA payload helpers
# ============================================================
def _text(t: str) -> Dict[str, Any]:
    return {"type": "text", "text": (t or "").strip()}


def _buttons(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    # formato que você já usa no app.py
    return {"type": "buttons", "text": (text or "").strip(), "buttons": buttons}


def _menu_cta() -> Dict[str, Any]:
    return _buttons(
        "Beleza. Qual é o foco agora?",
        [
            {"id": "FLOW_AUTOMATIZAR", "title": "Automação"},
            {"id": "FLOW_SITE", "title": "Site / E-commerce"},
            {"id": "FLOW_SOCIAL", "title": "Social / Tráfego"},
        ],
    )


# ============================================================
# Normalização
# ============================================================
def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _is_focus_payload(raw: str) -> bool:
    r = (raw or "").strip()
    l = _norm(r)
    return r in {"FLOW_AUTOMATIZAR", "FLOW_SITE", "FLOW_SOCIAL"} or l in {
        "automação", "automacao",
        "site / e-commerce", "site / ecommerce", "site", "e-commerce", "ecommerce",
        "social / tráfego", "social / trafego", "social", "tráfego", "trafego",
    }


def _focus_from_payload(raw: str) -> str:
    r = (raw or "").strip()
    l = _norm(r)

    if r == "FLOW_AUTOMATIZAR" or l in {"automação", "automacao"}:
        return "automacao"
    if r == "FLOW_SITE" or l in {"site / e-commerce", "site / ecommerce", "site", "e-commerce", "ecommerce"}:
        return "site"
    if r == "FLOW_SOCIAL" or l in {"social / tráfego", "social / trafego", "social", "tráfego", "trafego"}:
        return "social"
    return "indefinido"


# ============================================================
# Step builders
# ============================================================
def _ask_service_type(foco: str) -> Dict[str, Any]:
    if foco == "automacao":
        return _buttons(
            "Qual tipo de automação você quer?",
            [
                {"id": "AUTO_WPP", "title": "WhatsApp / Atendimento"},
                {"id": "AUTO_N8N", "title": "Automações (n8n / integrações)"},
                {"id": "AUTO_CRM", "title": "CRM / Funil / Pipeline"},
            ],
        )
    if foco == "site":
        return _buttons(
            "O que você precisa no digital?",
            [
                {"id": "SITE_LP", "title": "Landing Page"},
                {"id": "SITE_SITE", "title": "Site institucional"},
                {"id": "SITE_ECOM", "title": "E-commerce"},
            ],
        )
    # social
    return _buttons(
        "Qual é a prioridade agora?",
        [
            {"id": "SOCIAL_CONTEUDO", "title": "Conteúdo / Linha editorial"},
            {"id": "SOCIAL_TRAFEGO", "title": "Tráfego pago"},
            {"id": "SOCIAL_FULL", "title": "Social + Tráfego"},
        ],
    )


def _ask_deadline() -> Dict[str, Any]:
    return _buttons(
        "Qual prazo você pretende ter isso rodando?",
        [
            {"id": "PRAZO_7D", "title": "Até 7 dias"},
            {"id": "PRAZO_15D", "title": "15–20 dias"},
            {"id": "PRAZO_30D", "title": "30+ dias"},
        ],
    )


def _ask_budget() -> Dict[str, Any]:
    return _buttons(
        "Quanto você tem disponível para investir?",
        [
            {"id": "BUDGET_1", "title": "Até R$ 1.000"},
            {"id": "BUDGET_3", "title": "R$ 1.000 – R$ 3.000"},
            {"id": "BUDGET_5", "title": "R$ 3.000 – R$ 5.000"},
            {"id": "BUDGET_10", "title": "R$ 5.000+"},
        ],
    )


def _ask_company_and_ig() -> Dict[str, Any]:
    return _text("Qual o nome da empresa e o link do Instagram? (ex: MinhaMarca — https://instagram.com/minhamarca)")


def _ask_how_found() -> Dict[str, Any]:
    return _buttons(
        "Como você conheceu a Mugô?",
        [
            {"id": "ORIGEM_INDIC", "title": "Indicação"},
            {"id": "ORIGEM_INST", "title": "Instagram"},
            {"id": "ORIGEM_GOOG", "title": "Google"},
            {"id": "ORIGEM_OUTRO", "title": "Outro"},
        ],
    )


def _map_choice_to_value(choice_id: str, title: str) -> str:
    # salva o ID + title se quiser
    cid = (choice_id or "").strip()
    ttl = (title or "").strip()
    return cid or ttl


def _is_ig_line(text: str) -> bool:
    t = _norm(text)
    # aceita "Empresa - @insta" ou link etc.
    return ("instagram.com" in t) or ("@" in t) or (len(t) >= 3)


def _build_summary(data: Dict[str, Any]) -> str:
    foco = data.get("foco", "")
    tipo = data.get("tipo", "")
    prazo = data.get("prazo", "")
    budget = data.get("budget", "")
    empresa = data.get("empresa_instagram", "")
    origem = data.get("origem", "")

    return (
        f"Mini briefing:\n"
        f"- Foco: {foco}\n"
        f"- Tipo: {tipo}\n"
        f"- Prazo: {prazo}\n"
        f"- Investimento: {budget}\n"
        f"- Empresa/Instagram: {empresa}\n"
        f"- Origem: {origem}\n"
    ).strip()


# ============================================================
# MAIN
# ============================================================
def handle_mugo_flow(wa_id: str, user_input: str, *, choice_id: str = "") -> Optional[Dict[str, Any]]:
    """
    Retorna um payload do WhatsApp (type: text/buttons/list) ou
    {"type":"ai","user_message":"...","flow_context":{...}} quando finalizar.
    Retorna None se não quer capturar (deixa IA normal responder).
    """
    ui = (user_input or "").strip()
    if not wa_id or not ui:
        return None

    state, data = _flow_get(wa_id)
    if not isinstance(data, dict):
        data = {}

    # debug
    if DEBUG_FLOW:
        print(f"[FLOW] wa_id={wa_id} state={state} input={ui} choice_id={choice_id} data_keys={list(data.keys())}")

    # ============================================================
    # 1) MENU PRINCIPAL (mugo_cta)
    # ============================================================
    if state in ("", "mugo_cta", None):
        # ✅ CORREÇÃO DO SEU BUG: se vier FLOW_* tem que AVANÇAR
        if _is_focus_payload(ui):
            foco = _focus_from_payload(ui)
            data["foco"] = foco
            state = "step_tipo"
            _flow_save(wa_id, state, data)
            return _ask_service_type(foco)

        # Se mandar "oi", "olá" etc e não for escolha: mostra menu
        if _norm(ui) in {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "menu"}:
            _flow_save(wa_id, "mugo_cta", data)
            return _menu_cta()

        # Não capturou: deixa a IA normal tocar
        return None

    # ============================================================
    # 2) STEP TIPO (botões)
    # ============================================================
    if state == "step_tipo":
        # se a pessoa apertar os botões do menu de novo, mantém consistência
        if _is_focus_payload(ui):
            data["foco"] = _focus_from_payload(ui)
            _flow_save(wa_id, "step_tipo", data)
            return _ask_service_type(data.get("foco", "social"))

        # aqui esperamos IDs tipo AUTO_WPP / SITE_ECOM / SOCIAL_TRAFEGO
        data["tipo"] = _map_choice_to_value(choice_id or ui, ui)
        state = "step_prazo"
        _flow_save(wa_id, state, data)
        return _ask_deadline()

    # ============================================================
    # 3) STEP PRAZO (botões)
    # ============================================================
    if state == "step_prazo":
        data["prazo"] = _map_choice_to_value(choice_id or ui, ui)
        state = "step_budget"
        _flow_save(wa_id, state, data)
        return _ask_budget()

    # ============================================================
    # 4) STEP BUDGET (botões)
    # ============================================================
    if state == "step_budget":
        data["budget"] = _map_choice_to_value(choice_id or ui, ui)
        state = "step_empresa"
        _flow_save(wa_id, state, data)
        return _ask_company_and_ig()

    # ============================================================
    # 5) STEP EMPRESA + IG (texto)
    # ============================================================
    if state == "step_empresa":
        # se o usuário clicar algum botão perdido, não quebra:
        if _is_focus_payload(ui):
            # ele voltou a mexer no menu; reinicia pro tipo do novo foco
            data = {"foco": _focus_from_payload(ui)}
            state = "step_tipo"
            _flow_save(wa_id, state, data)
            return _ask_service_type(data["foco"])

        if not _is_ig_line(ui):
            return _text("Me manda assim: Nome da empresa + Instagram (link ou @).")

        data["empresa_instagram"] = ui
        state = "step_origem"
        _flow_save(wa_id, state, data)
        return _ask_how_found()

    # ============================================================
    # 6) STEP ORIGEM (botões) -> FINALIZA
    # ============================================================
    if state == "step_origem":
        data["origem"] = _map_choice_to_value(choice_id or ui, ui)

        summary = _build_summary(data)
        flow_context = {
            "flow": "mini_briefing_mugo",
            "state": "done",
            "data": data,
            "summary": summary,
        }

        # marca como finalizado no flow_state
        _flow_save(wa_id, "done", data)

        return {
            "type": "ai",
            "user_message": summary,
            "flow_context": flow_context,
        }

    # ============================================================
    # DONE: se já finalizou, deixa IA normal tocar (ou volta menu se quiser)
    # ============================================================
    if state == "done":
        return None

    # estado desconhecido: reseta para menu
    _flow_save(wa_id, "mugo_cta", {})
    return _menu_cta()