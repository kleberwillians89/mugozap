from datetime import datetime, timezone
from typing import Dict, Any

from services.state import list_conversations, merge_flow_data
from services.ai_state import get_ai_state, upsert_ai_state
from services.workspace import DEFAULT_WORKSPACE_ID, resolve_workspace_id
from services.whatsapp import send_message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _hours_since(dt_str: str) -> float:
    dt = _parse_dt(dt_str)
    if not dt:
        return 0
    delta = _now() - dt
    return delta.total_seconds() / 3600


def _build_followup_text(stage: str, memory_summary: str = "") -> str:
    memory_summary = (memory_summary or "").strip()

    if stage == "11h":
        if memory_summary:
            return f"Oi! Passando para retomar nosso contato. Pelo que entendi, você quer avançar em: {memory_summary}\n\nSe fizer sentido, me responde por aqui e seguimos."
        return "Oi! Passando para retomar nosso contato. Se ainda fizer sentido, me responde por aqui e seguimos."

    return "Oi! Estou por aqui para continuar."


async def _should_send_followup(conv: Dict[str, Any], workspace_id: str = "") -> str | None:
    wa_id = (conv.get("wa_id") or "").strip()
    if not wa_id:
        return None

    last_in_at = conv.get("last_in_at") or ""
    last_out_at = conv.get("last_out_at") or ""

    if not last_out_at:
        return None

    ai_state = await get_ai_state(wa_id, workspace_id=workspace_id)
    if not bool(ai_state.get("handoff_done")):
        return None

    sent_map = ai_state.get("followups_sent") or {}

    hours_from_out = _hours_since(last_out_at)

    # só envia se o cliente não respondeu depois da última saída
    if last_in_at and _parse_dt(last_in_at) and _parse_dt(last_out_at):
        if _parse_dt(last_in_at) > _parse_dt(last_out_at):
            return None

    if hours_from_out >= 11 and not sent_map.get("11h"):
        return "11h"

    return None


async def process_followups(workspace_id: str = "") -> Dict[str, Any]:
    workspace_id = resolve_workspace_id(explicit_workspace_id=workspace_id) or DEFAULT_WORKSPACE_ID
    conversations = list_conversations(limit=300, workspace_id=workspace_id) or []
    sent_total = 0
    checked = 0

    for conv in conversations:
        checked += 1
        wa_id = (conv.get("wa_id") or "").strip()
        if not wa_id:
            continue

        stage = await _should_send_followup(conv, workspace_id=workspace_id)
        if not stage:
            continue

        ai_state = await get_ai_state(wa_id, workspace_id=workspace_id)
        memory_summary = (ai_state.get("memory_summary") or "").strip()

        text = _build_followup_text(stage, memory_summary=memory_summary)

        try:
            send_message(wa_id, text)

            sent_map = ai_state.get("followups_sent") or {}
            sent_map[stage] = _now().isoformat()

            await upsert_ai_state(
                wa_id,
                {
                    **ai_state,
                    "followups_sent": sent_map,
                    "last_followup_stage": stage,
                    "last_followup_at": _now().isoformat(),
                },
                workspace_id=workspace_id,
            )
            merge_flow_data(
                wa_id,
                {
                    "last_bot_step": "reengagement_11h",
                    "last_bot_text": text[:900],
                    "last_bot_at": _now().isoformat(),
                    "reengagement_11h_sent_at": sent_map[stage],
                    "waiting_after_handoff": True,
                    "bot_paused": True,
                    "bot_status": "followup_scheduled",
                    "followup_due_at": sent_map[stage],
                    "waiting_for": "customer",
                },
                workspace_id=workspace_id,
            )
            print(f"FLOW:followup wa_id={wa_id} status=followup_scheduled step=reengagement_11h")

            sent_total += 1

        except Exception:
            continue

    return {"ok": True, "checked": checked, "sent": sent_total, "workspace_id": workspace_id}
