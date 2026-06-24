begin;

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  workspace_id text not null default 'workspace-mugo-default',
  name text not null default '',
  email text not null,
  role text not null default 'atendimento',
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint profiles_role_check check (role in ('admin', 'gestor', 'atendimento'))
);

create unique index if not exists ux_profiles_workspace_email
  on public.profiles (workspace_id, lower(email));

create index if not exists idx_profiles_workspace_role
  on public.profiles (workspace_id, role);

alter table public.profiles enable row level security;

alter table if exists public.whatsapp_users
  add column if not exists status text,
  add column if not exists owner text,
  add column if not exists assigned_to text,
  add column if not exists human_owner text,
  add column if not exists closed_at timestamptz,
  add column if not exists source text,
  add column if not exists last_source text,
  add column if not exists campaign text,
  add column if not exists tags jsonb,
  add column if not exists lead_score integer,
  add column if not exists lead_temperature text,
  add column if not exists lead_theme text,
  add column if not exists lead_stage text,
  add column if not exists priority integer,
  add column if not exists flow_state text,
  add column if not exists flow_data jsonb,
  add column if not exists entry_type text,
  add column if not exists inbound_type text,
  add column if not exists attendance_mode text,
  add column if not exists automation_paused boolean,
  add column if not exists bot_enabled boolean,
  add column if not exists company text,
  add column if not exists email text,
  add column if not exists segment text,
  add column if not exists instagram text,
  add column if not exists site text,
  add column if not exists linkedin text,
  add column if not exists google_business text,
  add column if not exists service text,
  add column if not exists service_interest text,
  add column if not exists service_contracted text;

alter table if exists public.whatsapp_conversations
  add column if not exists status text,
  add column if not exists owner text,
  add column if not exists assigned_to text,
  add column if not exists human_owner text,
  add column if not exists closed_at timestamptz,
  add column if not exists source text,
  add column if not exists last_source text,
  add column if not exists campaign text,
  add column if not exists tags jsonb,
  add column if not exists lead_score integer,
  add column if not exists lead_temperature text,
  add column if not exists lead_theme text,
  add column if not exists lead_stage text,
  add column if not exists priority integer,
  add column if not exists flow_state text,
  add column if not exists flow_data jsonb,
  add column if not exists entry_type text,
  add column if not exists inbound_type text,
  add column if not exists attendance_mode text,
  add column if not exists automation_paused boolean,
  add column if not exists bot_enabled boolean,
  add column if not exists company text,
  add column if not exists email text,
  add column if not exists segment text,
  add column if not exists instagram text,
  add column if not exists site text,
  add column if not exists linkedin text,
  add column if not exists google_business text,
  add column if not exists service text,
  add column if not exists service_interest text,
  add column if not exists service_contracted text;

commit;
