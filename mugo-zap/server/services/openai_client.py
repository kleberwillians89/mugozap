# mugo-zap/server/services/openai_client.py
import os
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

# carrega .env da raiz do repo (mugozap/.env)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)


def generate_reply(
    wa_id: str,
    user_message: str,
    first_message_sent: bool,
    name: str = "",
    telefone: str = "",
) -> Dict[str, Any]:
    """
    Função mínima e estável só pra NÃO quebrar o deploy.
    Depois você evolui a IA aqui.
    """
    text = (user_message or "").strip().lower()

    # heurísticas rápidas (mantém seu app.py funcionando)
    if any(k in text for k in ["orçamento", "orcamento", "preço", "preco", "valor", "prazo", "contrato", "fechar"]):
        return {
            "reply": "Perfeito. Vou direcionar você agora para um dos nossos especialistas dar sequência estratégica ao seu projeto.",
            "intent": "handoff",
            "question_key": "none",
            "handoff": True,
            "handoff_summary": user_message[:180],
            "next_intent": "handoff",
            "lead_score": 90,
            "lead_temperature": "quente",
            "lead_theme": "indefinido",
        }

    # resposta padrão curta
    return {
        "reply": "Em uma frase: o que você quer destravar agora?",
        "intent": "geral",
        "question_key": "none",
        "handoff": False,
        "handoff_summary": "",
        "next_intent": "next",
        "lead_score": 10,
        "lead_temperature": "frio",
        "lead_theme": "indefinido",
    }