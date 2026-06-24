from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional

WELCOME_MESSAGE = (
    "Olá, tudo bem? Seja bem-vindo à Mugô.\n\n"
    "Somos uma agência de soluções tecnológicas que une marketing, automação, inteligência artificial, sites, CRM e dados para ajudar empresas a crescerem com mais estrutura.\n\n"
    "Para entendermos melhor seu momento, faça nosso diagnóstico gratuito pelo link abaixo:\n\n"
    "https://intelligence.mugoagencia.com.br/\n\n"
    "Assim que você finalizar, seguimos seu atendimento por aqui."
)

INTELLIGENCE_COMPLETION_HISTORY_EVENT = "Diagnóstico Mugô Intelligence concluído pelo lead no WhatsApp"

QUEUE_OPTIONS = [
    "Novos leads",
    "Clientes ativos",
    "Cobrança",
    "Suporte",
    "Orçamentos",
    "Automações",
]

STATUS_OPTIONS = [
    "Novo lead",
    "Diagnóstico enviado",
    "Diagnóstico recebido",
    "Diagnóstico concluído",
    "Briefing recebido",
    "Cliente ativo",
    "Cobrança em aberto",
    "Cobrança paga",
    "Cobrança atrasada",
]


def _plain_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def is_mugo_intelligence_completion_message(value: Any) -> bool:
    text = _plain_text(value)
    return "acabei de concluir o diagnostico mugo" in text


def _has_real_diagnosis_text(value: Any) -> bool:
    text = str(value or "").strip()
    plain = _plain_text(text)
    return bool(text) and plain not in {"indefinido", "sem recomendacao", "sem leitura", "nao informado"}


def build_intelligence_completion_confirmation(opportunity: Any = "", recommended_service: Any = "") -> str:
    opportunity_text = str(opportunity or "").strip()
    service_text = str(recommended_service or "").strip()

    if _has_real_diagnosis_text(opportunity_text) and _has_real_diagnosis_text(service_text):
        return (
            "Recebemos seu Diagnóstico Mugô.\n\n"
            "Com base nas suas respostas, identificamos uma oportunidade clara para evoluir sua operação:\n\n"
            f"{opportunity_text}\n\n"
            "O caminho recomendado pela Mugô é:\n\n"
            f"{service_text}\n\n"
            "Nosso time vai analisar seu cenário com mais profundidade e seguir por aqui com uma orientação prática sobre os próximos passos."
        )

    return (
        "Recebemos seu Diagnóstico Mugô.\n\n"
        "Nosso time vai analisar suas respostas com cuidado e seguir por aqui com uma orientação prática sobre os próximos passos."
    )


def normalize_queue(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "novos leads": "Novos leads",
        "novos_leads": "Novos leads",
        "novos": "Novos leads",
        "clientes ativos": "Clientes ativos",
        "clientes_ativos": "Clientes ativos",
        "clientes": "Clientes ativos",
        "cobranca": "Cobrança",
        "cobrança": "Cobrança",
        "cobranca_em_aberto": "Cobrança",
        "suporte": "Suporte",
        "orçamentos": "Orçamentos",
        "orcamentos": "Orçamentos",
        "automações": "Automações",
        "automacoes": "Automações",
    }
    return mapping.get(raw, "Novos leads")


def normalize_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "novo lead": "Novo lead",
        "novo_lead": "Novo lead",
        "novo": "Novo lead",
        "diagnostico concluido": "Diagnóstico concluído",
        "diagnóstico concluído": "Diagnóstico concluído",
        "diagnostico_concluido": "Diagnóstico concluído",
        "diagnostico": "Diagnóstico concluído",
        "diagnostico recebido": "Diagnóstico recebido",
        "diagnóstico recebido": "Diagnóstico recebido",
        "diagnostico_recebido": "Diagnóstico recebido",
        "briefing recebido": "Briefing recebido",
        "briefing_recebido": "Briefing recebido",
        "welcome_completed": "Briefing recebido",
        "cliente ativo": "Cliente ativo",
        "cliente_ativo": "Cliente ativo",
        "cliente": "Cliente ativo",
        "cobranca em aberto": "Cobrança em aberto",
        "cobrança em aberto": "Cobrança em aberto",
        "cobranca_aberta": "Cobrança em aberto",
        "cobranca paga": "Cobrança paga",
        "cobrança paga": "Cobrança paga",
        "cobranca_paga": "Cobrança paga",
        "cobranca atrasada": "Cobrança atrasada",
        "cobrança atrasada": "Cobrança atrasada",
        "cobranca_atrasada": "Cobrança atrasada",
    }
    return mapping.get(raw, "Novo lead")


def build_welcome_message() -> str:
    return WELCOME_MESSAGE


def build_collection_reminder_message(amount: Any = "", due_date: Any = "") -> str:
    amount_text = str(amount or "").strip()
    due_text = str(due_date or "").strip()
    if amount_text and due_text:
        return f"Olá! Este é um lembrete de cobrança da Mugô no valor de {amount_text} para {due_text}. Favor confirmar o pagamento ou entrar em contato conosco."
    if amount_text:
        return f"Olá! Este é um lembrete de cobrança da Mugô no valor de {amount_text}. Favor confirmar o pagamento ou entrar em contato conosco."
    return "Olá! Este é um lembrete de cobrança da Mugô. Favor confirmar o pagamento ou entrar em contato conosco."


def build_diagnosis_summary(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
    full_answers = (
        fields.get("full_answers")
        or fields.get("respostas_completas")
        or payload.get("full_answers")
        or payload.get("respostas_completas")
        or {}
    )
    return {
        "lead_id": str(fields.get("lead_id") or payload.get("lead_id") or "").strip(),
        "name": str(
            fields.get("name")
            or fields.get("nome")
            or fields.get("responsavel")
            or fields.get("responsible")
            or payload.get("name")
            or payload.get("nome")
            or payload.get("responsavel")
            or payload.get("responsible")
            or ""
        ).strip(),
        "company": str(fields.get("company") or fields.get("empresa") or payload.get("company") or payload.get("empresa") or "").strip(),
        "phone": str(fields.get("phone") or fields.get("telefone") or payload.get("phone") or payload.get("telefone") or "").strip(),
        "email": str(fields.get("email") or payload.get("email") or "").strip(),
        "segment": str(fields.get("segment") or fields.get("segmento") or payload.get("segment") or payload.get("segmento") or "").strip(),
        "instagram": str(fields.get("instagram") or payload.get("instagram") or "").strip(),
        "site": str(fields.get("site") or payload.get("site") or "").strip(),
        "linkedin": str(fields.get("linkedin") or payload.get("linkedin") or "").strip(),
        "google_business": str(fields.get("google_business") or payload.get("google_business") or "").strip(),
        "score_overall": str(fields.get("score_overall") or fields.get("score_geral") or payload.get("score_overall") or payload.get("score_geral") or "").strip(),
        "score_marketing": str(fields.get("score_marketing") or payload.get("score_marketing") or "").strip(),
        "score_sales": str(fields.get("score_sales") or fields.get("score_vendas") or payload.get("score_sales") or payload.get("score_vendas") or "").strip(),
        "score_automation": str(fields.get("score_automation") or fields.get("score_automacao") or payload.get("score_automation") or payload.get("score_automacao") or "").strip(),
        "score_data": str(fields.get("score_data") or fields.get("score_dados") or payload.get("score_data") or payload.get("score_dados") or "").strip(),
        "score_relationship": str(fields.get("score_relationship") or fields.get("score_relacionamento") or payload.get("score_relationship") or payload.get("score_relacionamento") or "").strip(),
        "opportunity": str(fields.get("opportunity") or fields.get("principal_oportunidade") or payload.get("opportunity") or payload.get("principal_oportunidade") or "").strip(),
        "recommended_service": str(fields.get("recommended_service") or fields.get("servico_mugo_recomendado") or payload.get("recommended_service") or payload.get("servico_mugo_recomendado") or "").strip(),
        "summary": str(fields.get("summary") or fields.get("resumo_gerado") or payload.get("summary") or payload.get("resumo_gerado") or "").strip(),
        "full_answers": full_answers,
        "temperature": str(fields.get("temperature") or fields.get("temperatura") or payload.get("temperature") or payload.get("temperatura") or "").strip(),
        "origin": str(fields.get("origin") or fields.get("origem_lead") or payload.get("origin") or payload.get("origem_lead") or "").strip(),
        "utm_source": str(fields.get("utm_source") or payload.get("utm_source") or "").strip(),
        "utm_medium": str(fields.get("utm_medium") or payload.get("utm_medium") or "").strip(),
        "utm_campaign": str(fields.get("utm_campaign") or payload.get("utm_campaign") or "").strip(),
    }


def build_welcome_summary(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
    return {
        "lead_id": str(fields.get("lead_id") or payload.get("lead_id") or "").strip(),
        "company": str(fields.get("company") or fields.get("empresa") or payload.get("company") or payload.get("empresa") or "").strip(),
        "responsible": str(fields.get("responsible") or fields.get("responsavel") or payload.get("responsible") or payload.get("responsavel") or "").strip(),
        "phone": str(fields.get("phone") or fields.get("telefone") or payload.get("phone") or payload.get("telefone") or "").strip(),
        "email": str(fields.get("email") or payload.get("email") or "").strip(),
        "cnpj": str(fields.get("cnpj") or payload.get("cnpj") or "").strip(),
        "site": str(fields.get("site") or payload.get("site") or "").strip(),
        "instagram": str(fields.get("instagram") or payload.get("instagram") or "").strip(),
        "services": str(fields.get("services") or fields.get("servicos") or payload.get("services") or payload.get("servicos") or "").strip(),
        "target_audience": str(fields.get("target_audience") or fields.get("publico_alvo") or payload.get("target_audience") or payload.get("publico_alvo") or "").strip(),
        "differentials": str(fields.get("differentials") or fields.get("diferenciais") or payload.get("differentials") or payload.get("diferenciais") or "").strip(),
        "goals": str(fields.get("goals") or fields.get("objetivos") or payload.get("goals") or payload.get("objetivos") or "").strip(),
        "metrics": str(fields.get("metrics") or fields.get("metricas") or payload.get("metrics") or payload.get("metricas") or "").strip(),
        "voice_tone": str(fields.get("voice_tone") or fields.get("tom_de_voz") or payload.get("voice_tone") or payload.get("tom_de_voz") or "").strip(),
        "competitors": str(fields.get("competitors") or fields.get("concorrentes") or payload.get("competitors") or payload.get("concorrentes") or "").strip(),
        "references": str(fields.get("references") or fields.get("referencias") or payload.get("references") or payload.get("referencias") or "").strip(),
        "frequency": str(fields.get("frequency") or fields.get("frequencia") or payload.get("frequency") or payload.get("frequencia") or "").strip(),
        "challenges": str(fields.get("challenges") or fields.get("desafios") or payload.get("challenges") or payload.get("desafios") or "").strip(),
        "budget": str(fields.get("budget") or fields.get("orcamento") or payload.get("budget") or payload.get("orcamento") or "").strip(),
        "deadline": str(fields.get("deadline") or fields.get("prazo") or payload.get("deadline") or payload.get("prazo") or "").strip(),
        "notes": str(fields.get("notes") or fields.get("observacoes") or payload.get("notes") or payload.get("observacoes") or "").strip(),
        "origin": str(fields.get("origin") or fields.get("origem_lead") or payload.get("origin") or payload.get("origem_lead") or "").strip(),
        "utm_source": str(fields.get("utm_source") or payload.get("utm_source") or "").strip(),
        "utm_medium": str(fields.get("utm_medium") or payload.get("utm_medium") or "").strip(),
        "utm_campaign": str(fields.get("utm_campaign") or payload.get("utm_campaign") or "").strip(),
    }


def make_contact_profile(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    return {
        "name": str(payload.get("name") or "").strip(),
        "company": str(payload.get("company") or "").strip(),
        "telefone": str(payload.get("telefone") or payload.get("phone") or "").strip(),
        "email": str(payload.get("email") or "").strip(),
        "service": str(payload.get("service") or payload.get("service_contratado") or "").strip(),
        "owner": str(payload.get("owner") or payload.get("responsible") or "").strip(),
        "status": normalize_status(payload.get("status") or "Cliente ativo"),
        "queue": normalize_queue(payload.get("queue") or "Clientes ativos"),
        "notes": str(payload.get("notes") or "").strip(),
    }


def build_summary_payload(existing: Optional[Dict[str, Any]], diagnosis: Optional[Dict[str, Any]], queue: Any = None, status: Any = None, owner: Any = None) -> Dict[str, Any]:
    base = dict(existing or {})
    base["diagnosis"] = build_diagnosis_summary(diagnosis)
    base["queue"] = normalize_queue(queue or base.get("queue") or "Novos leads")
    base["status"] = normalize_status(status or base.get("status") or "Novo lead")
    base["owner"] = str(owner or base.get("owner") or "").strip()
    base["diagnosis_ready"] = bool(base["diagnosis"].get("name") or base["diagnosis"].get("company") or base["diagnosis"].get("email") or base["diagnosis"].get("phone"))
    return base
