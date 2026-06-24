begin;

alter table if exists public.whatsapp_users
  add column if not exists automation_stage text,
  add column if not exists internal_diagnosis_notified_at timestamptz;

alter table if exists public.whatsapp_conversations
  add column if not exists automation_stage text,
  add column if not exists internal_diagnosis_notified_at timestamptz;

commit;
