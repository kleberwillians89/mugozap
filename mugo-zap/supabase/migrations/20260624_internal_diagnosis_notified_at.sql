begin;

alter table if exists public.whatsapp_users
  add column if not exists origem_lead text,
  add column if not exists segment text,
  add column if not exists segmento text,
  add column if not exists score_geral text,
  add column if not exists score_marketing text,
  add column if not exists score_vendas text,
  add column if not exists score_automacao text,
  add column if not exists score_dados text,
  add column if not exists score_relacionamento text,
  add column if not exists principal_oportunidade text,
  add column if not exists servico_mugo_recomendado text,
  add column if not exists resumo_gerado text,
  add column if not exists respostas_completas jsonb,
  add column if not exists intelligence_received_at timestamptz,
  add column if not exists automation_stage text,
  add column if not exists internal_diagnosis_notified_at timestamptz;

alter table if exists public.whatsapp_conversations
  add column if not exists origem_lead text,
  add column if not exists segment text,
  add column if not exists segmento text,
  add column if not exists score_geral text,
  add column if not exists score_marketing text,
  add column if not exists score_vendas text,
  add column if not exists score_automacao text,
  add column if not exists score_dados text,
  add column if not exists score_relacionamento text,
  add column if not exists principal_oportunidade text,
  add column if not exists servico_mugo_recomendado text,
  add column if not exists resumo_gerado text,
  add column if not exists respostas_completas jsonb,
  add column if not exists intelligence_received_at timestamptz,
  add column if not exists automation_stage text,
  add column if not exists internal_diagnosis_notified_at timestamptz;

commit;
