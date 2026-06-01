begin;

alter table if exists public.whatsapp_conversations
  add column if not exists workspace_id text;
update public.whatsapp_conversations
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_whatsapp_conversations_workspace_id
  on public.whatsapp_conversations (workspace_id);

alter table if exists public.whatsapp_messages
  add column if not exists workspace_id text;
update public.whatsapp_messages
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_whatsapp_messages_workspace_id
  on public.whatsapp_messages (workspace_id);
create index if not exists idx_whatsapp_messages_workspace_wa_id
  on public.whatsapp_messages (workspace_id, wa_id);

alter table if exists public.whatsapp_tasks
  add column if not exists workspace_id text;
update public.whatsapp_tasks
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_whatsapp_tasks_workspace_id
  on public.whatsapp_tasks (workspace_id);

alter table if exists public.whatsapp_users
  add column if not exists workspace_id text;
update public.whatsapp_users
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_whatsapp_users_workspace_id
  on public.whatsapp_users (workspace_id);

alter table if exists public.whatsapp_flow_state
  add column if not exists workspace_id text;
update public.whatsapp_flow_state
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_whatsapp_flow_state_workspace_id
  on public.whatsapp_flow_state (workspace_id);

alter table if exists public.ai_state
  add column if not exists workspace_id text;
update public.ai_state
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
create index if not exists idx_ai_state_workspace_id
  on public.ai_state (workspace_id);

commit;
