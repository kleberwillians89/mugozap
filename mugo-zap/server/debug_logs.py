# server/debug_logs.py
import json
from services.state import list_conversations, get_recent_messages

def analisar_erros():
    print("🔍 BUSCANDO AS ÚLTIMAS CONVERSAS NO SUPABASE...\n")
    
    # Puxa as 3 conversas mais recentes
    conversas = list_conversations(limit=3)
    
    if not conversas:
        print("Nenhuma conversa encontrada. O Webhook pode não estar salvando no banco.")
        return

    for c in conversas:
        wa_id = c.get('wa_id')
        nome = c.get('name') or 'Sem Nome'
        handoff = c.get('handoff_active')
        
        print("="*50)
        print(f"👤 CONTATO: {nome} | WA_ID: {wa_id} | HANDOFF ATIVO: {handoff}")
        print("-" * 50)
        
        # Puxa as últimas 5 mensagens dessa pessoa
        mensagens = get_recent_messages(wa_id, limit=5)
        
        if not mensagens:
            print("Nenhuma mensagem encontrada para este contato.")
        
        for m in mensagens:
            direcao = "🟢 [CLIENTE]" if m.get('direction') == 'in' else "🤖 [MUGÔZAP]"
            texto = m.get('text', '')
            meta = m.get('meta') or {}
            
            print(f"{direcao}: {texto}")
            
            # Se houver erro salvo no JSON da mensagem, ele avisa aqui
            if meta.get("error"):
                print(f"   ⚠️ ERRO DA IA/SISTEMA: {meta.get('error')}")
            
            # Se a IA respondeu um JSON estranho, mostra aqui
            if meta.get("intent"):
                print(f"   🧠 [Intent: {meta.get('intent')} | Handoff: {meta.get('handoff')}]")
                
        print("="*50, "\n")

if __name__ == "__main__":
    analisar_erros()