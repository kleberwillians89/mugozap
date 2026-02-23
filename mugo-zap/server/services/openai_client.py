import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
from openai import OpenAI

try:
    from services.state import get_recent_messages
except Exception:
    from .state import get_recent_messages


# ============================================================
# ENV
# ============================================================
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

if not OPENAI_API_KEY:
    raise RuntimeError("ENV faltando: OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = """
Você é o consultor de novos negócios da Mugô no WhatsApp.

Fale como alguém experiente e direto.
Sem formalidade exagerada.
Sem frases padrão de robô.
Sem repetir "Entendi".
Sem parecer script.

FORMA
- Natural.
- Direto.
- No máximo 2 frases.
- Apenas 1 pergunta quando necessário.
- Sem emojis.
- Sem markdown.

COMPORTAMENTO
- Se o cliente for claro, aprofunde.
- Se for vago, faça pergunta binária.
- Se falar de preço, orçamento, prazo ou fechar: transfira.
- Se ficar rodando: transfira.

TRANSFERÊNCIA (não altere texto)
Se mencionar preço, valor, orçamento, proposta, prazo, contrato ou quiser fechar:
"Perfeito. Vou direcionar você agora para um dos nossos especialistas dar sequência estratégica ao seu projeto."

Se estiver rodando:
"Para aprofundarmos isso da forma certa, vou direcionar você agora para um especialista do nosso time."
""".strip()


# ============================================================
# LINGUAGEM NATURAL (ANTI-ROBÔ)
# ============================================================
FORBIDDEN_OPENINGS = [
    "entendi",
    "entendo",
    "com certeza",
    "perfeitamente",
    "claro,"
]

def clean_robotic_opening(text: str) -> str:
    t = (text or "").strip()
    lower = t.lower()

    for f in FORBIDDEN_OPENINGS:
        if lower.startswith(f):
            t = t[len(f):].lstrip(" ,.-")
            break

    t = re.sub(r"^entendi que\s+", "", t, flags=re.I)
    return t.strip()


# ============================================================
# DETECÇÕES
# ============================================================
def is_vague(text: str) -> bool:
    t = (text or "").strip().lower()
    words = re.findall(r"\w+", t)

    if len(words) <= 2:
        return True

    vague_terms = {
        "sim","não","nao","dinheiro","tempo","vendas",
        "marketing","site","preciso","quero","ajuda",
        "urgente","talvez"
    }

    if t in vague_terms:
        return True

    if "não sei" in t or "nao sei" in t:
        return True

    return False


def wants_handoff(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "valor","valores","preço","preco",
        "orçamento","orcamento","quanto custa",
        "prazo","contrato","proposta",
        "reunião","reuniao","fechar","pagamento"
    ]
    return any(k in t for k in triggers)


def asked_human(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "humano","atendente","pessoa",
        "falar com alguém","falar com alguem",
        "me liga","quero falar com uma pessoa"
    ]
    return any(k in t for k in triggers)


def count_questions(history: List[Dict[str, Any]], user_message: str) -> int:
    def is_question(text: str):
        return "?" in (text or "") or any(
            w in (text or "").lower()
            for w in ["quanto","como","qual","prazo","valor"]
        )

    msgs = [m for m in history if m.get("direction") == "in"]
    recent = msgs[-10:]
    count = sum(1 for m in recent if is_question(m.get("text") or ""))
    if is_question(user_message):
        count += 1
    return count


# ============================================================
# LEAD INTELIGÊNCIA
# ============================================================
def detect_theme(text: str) -> str:
    t = (text or "").lower()

    vendas = ["vendas","leads","funil","anuncio","tráfego","conversão","ticket","cliente"]
    operacao = ["processo","automação","crm","integração","tempo","equipe","sistema","gestão"]

    if any(k in t for k in vendas):
        return "vendas"
    if any(k in t for k in operacao):
        return "operacao"

    return "indefinido"


def detect_temperature(text: str) -> str:
    t = (text or "").lower()

    if any(k in t for k in ["urgente","essa semana","já invisto","já vendo","meta","escalar"]):
        return "quente"

    if any(k in t for k in ["quero melhorar","preciso organizar","estou começando"]):
        return "morno"

    return "frio"


def calculate_score(text: str, theme: str, temperature: str) -> int:
    score = 0
    t = (text or "").lower()

    if theme != "indefinido":
        score += 20

    if temperature == "morno":
        score += 20
    elif temperature == "quente":
        score += 40

    if any(k in t for k in ["meta","objetivo","ticket","faturamento","equipe"]):
        score += 20

    if any(k in t for k in ["já uso","já tenho","já faço"]):
        score += 20

    return min(score, 100)


def _history_to_lines(history: List[Dict[str, Any]], limit: int = 10) -> str:
    lines = []
    for m in history:
        role = "Usuário" if m.get("direction") == "in" else "Mugô"
        text = (m.get("text") or "").replace("\n", " ").strip()
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines[-limit:]) or "Sem histórico."


def _safe_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except:
        return {
            "reply": text.strip()[:800],
            "intent": "geral",
            "question_key": "none",
            "next_intent": "next"
        }


# ============================================================
# MAIN
# ============================================================
def generate_reply(
    wa_id: str,
    user_message: str,
    first_message_sent: bool,
    name: str = "",
    telefone: str = "",
) -> Dict[str, Any]:

    history = get_recent_messages(wa_id, limit=18)

    # Handoff direto
    if wants_handoff(user_message) or asked_human(user_message):
        return {
            "reply": "Perfeito. Vou direcionar você agora para um dos nossos especialistas dar sequência estratégica ao seu projeto.",
            "intent": "handoff",
            "question_key": "none",
            "handoff": True,
            "handoff_summary": "",
            "next_intent": "handoff",
            "lead_score": 100,
            "lead_temperature": "quente",
            "lead_theme": detect_theme(user_message)
        }

    if count_questions(history, user_message) >= 6:
        return {
            "reply": "Para aprofundarmos isso da forma certa, vou direcionar você agora para um especialista do nosso time.",
            "intent": "handoff",
            "question_key": "none",
            "handoff": True,
            "handoff_summary": "",
            "next_intent": "handoff_rodeo",
            "lead_score": 50,
            "lead_temperature": "morno",
            "lead_theme": detect_theme(user_message)
        }

    vague = is_vague(user_message)
    theme = detect_theme(user_message)
    temperature = detect_temperature(user_message)
    score = calculate_score(user_message, theme, temperature)

    # Lead quente vai direto
    if temperature == "quente" and score >= 60:
        return {
            "reply": "Perfeito. Vou direcionar você agora para um dos nossos especialistas dar sequência estratégica ao seu projeto.",
            "intent": "handoff_hot",
            "question_key": "none",
            "handoff": True,
            "handoff_summary": f"Tema: {theme} | Score: {score}",
            "next_intent": "handoff",
            "lead_score": score,
            "lead_temperature": temperature,
            "lead_theme": theme
        }

    history_block = _history_to_lines(history)

    if vague:
        instruction = "Pergunta binária. Processo ou sistema? Geração ou conversão? Seja direto."
    else:
        if theme == "vendas":
            instruction = "Aprofunde em geração ou conversão."
        elif theme == "operacao":
            instruction = "Aprofunde em processo, sistema ou equipe."
        else:
            instruction = "Defina se o foco é vendas ou operação."

    user_prompt = f"""
HISTÓRICO:
{history_block}

MENSAGEM:
{user_message}

INSTRUÇÃO:
{instruction}

Responda somente JSON com:
reply
intent
question_key
next_intent
"""

    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    data = _safe_json(resp.choices[0].message.content or "")
    reply = clean_robotic_opening(data.get("reply", ""))

    return {
        "reply": reply[:800],
        "intent": data.get("intent", "geral"),
        "question_key": data.get("question_key", "none"),
        "handoff": False,
        "handoff_summary": "",
        "next_intent": data.get("next_intent", "next"),
        "lead_score": score,
        "lead_temperature": temperature,
        "lead_theme": theme
    }