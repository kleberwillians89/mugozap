# mugo-zap/server/debug_logs.py
from services.state import list_conversations, get_recent_messages

def analisar_erros(limit_conversas: int = 5, limit_mensagens: int = 8):
    print("🔍 BUSCANDO CONVERSAS MAIS RECENTES...\n")

    conversas = list_conversations(limit=limit_conversas)

    if not conversas:
        print("Nenhuma conversa encontrada. O webhook pode não estar salvando no banco.")
        return

    for c in conversas:
        wa_id = c.get("wa_id")
        nome = c.get("name") or "Sem Nome"
        handoff = c.get("handoff_active")
        stage = c.get("stage") or c.get("lead_stage") or "-"
        assigned_to = c.get("assigned_to") or c.get("owner") or "-"
        source = c.get("source") or c.get("last_source") or "-"
        campaign = c.get("campaign") or "-"

        print("=" * 70)
        print(
            f"👤 CONTATO: {nome} | WA_ID: {wa_id}\n"
            f"📍 STAGE: {stage} | 👥 RESPONSÁVEL: {assigned_to} | "
            f"📣 ORIGEM: {source} | 🎯 CAMPANHA: {campaign} | HANDOFF: {handoff}"
        )
        print("-" * 70)

        mensagens = get_recent_messages(wa_id, limit=limit_mensagens)

        if not mensagens:
            print("Nenhuma mensagem encontrada para este contato.")
            continue

        for m in mensagens:
            direcao = "🟢 [CLIENTE]" if m.get("direction") == "in" else "🤖 [MUGÔZAP]"
            texto = (m.get("text") or "").strip()
            meta = m.get("meta") or {}

            print(f"{direcao}: {texto}")

            if meta.get("source") or meta.get("campaign"):
                print(
                    f"   📌 source={meta.get('source') or '-'} | "
                    f"campaign={meta.get('campaign') or '-'}"
                )

            if meta.get("error"):
                print(f"   ⚠️ ERRO: {meta.get('error')}")

            if meta.get("intent"):
                print(
                    f"   🧠 intent={meta.get('intent')} | "
                    f"handoff={meta.get('handoff')}"
                )

            if meta.get("cid"):
                print(f"   🔎 cid={meta.get('cid')}")

        print("=" * 70, "\n")


if __name__ == "__main__":
    analisar_erros()