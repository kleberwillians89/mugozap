begin;

create table if not exists public.workspaces (
  id text primary key,
  name text not null,
  slug text not null unique,
  is_default boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

insert into public.workspaces (id, name, slug, is_default)
values ('workspace-mugo-default', 'Mugo', 'mugo', true)
on conflict (id) do update
set
  name = excluded.name,
  slug = excluded.slug,
  is_default = true,
  updated_at = timezone('utc', now());

alter table if exists public.whatsapp_users
  add column if not exists workspace_id text;
update public.whatsapp_users
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.whatsapp_users
  alter column workspace_id set default 'workspace-mugo-default';
alter table if exists public.whatsapp_users
  alter column workspace_id set not null;
create index if not exists idx_whatsapp_users_workspace_id on public.whatsapp_users (workspace_id);
create unique index if not exists ux_whatsapp_users_workspace_wa_id
  on public.whatsapp_users (workspace_id, wa_id);

alter table if exists public.whatsapp_messages
  add column if not exists workspace_id text;
update public.whatsapp_messages
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.whatsapp_messages
  alter column workspace_id set default 'workspace-mugo-default';
alter table if exists public.whatsapp_messages
  alter column workspace_id set not null;
create index if not exists idx_whatsapp_messages_workspace_id on public.whatsapp_messages (workspace_id);
create index if not exists idx_whatsapp_messages_workspace_wa_created
  on public.whatsapp_messages (workspace_id, wa_id, created_at desc);

alter table if exists public.whatsapp_tasks
  add column if not exists workspace_id text;
update public.whatsapp_tasks
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.whatsapp_tasks
  alter column workspace_id set default 'workspace-mugo-default';
alter table if exists public.whatsapp_tasks
  alter column workspace_id set not null;
create index if not exists idx_whatsapp_tasks_workspace_id on public.whatsapp_tasks (workspace_id);
create index if not exists idx_whatsapp_tasks_workspace_status_due
  on public.whatsapp_tasks (workspace_id, status, due_at asc);

alter table if exists public.ai_state
  add column if not exists workspace_id text;
update public.ai_state
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.ai_state
  alter column workspace_id set default 'workspace-mugo-default';
alter table if exists public.ai_state
  alter column workspace_id set not null;
create index if not exists idx_ai_state_workspace_id on public.ai_state (workspace_id);
create unique index if not exists ux_ai_state_workspace_wa_id
  on public.ai_state (workspace_id, wa_id);

alter table if exists public.flow_state
  add column if not exists workspace_id text;
update public.flow_state
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.flow_state
  alter column workspace_id set default 'workspace-mugo-default';
create index if not exists idx_flow_state_workspace_id on public.flow_state (workspace_id);

alter table if exists public.settings
  add column if not exists workspace_id text;
update public.settings
set workspace_id = 'workspace-mugo-default'
where workspace_id is null or btrim(workspace_id) = '';
alter table if exists public.settings
  alter column workspace_id set default 'workspace-mugo-default';
create index if not exists idx_settings_workspace_id on public.settings (workspace_id);

do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema = 'public' and table_name = 'whatsapp_users'
  ) and not exists (
    select 1 from pg_constraint where conname = 'fk_whatsapp_users_workspace'
  ) then
    alter table public.whatsapp_users
      add constraint fk_whatsapp_users_workspace
      foreign key (workspace_id) references public.workspaces (id)
      on update cascade on delete restrict not valid;
    alter table public.whatsapp_users validate constraint fk_whatsapp_users_workspace;
  end if;
end $$;

do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema = 'public' and table_name = 'whatsapp_messages'
  ) and not exists (
    select 1 from pg_constraint where conname = 'fk_whatsapp_messages_workspace'
  ) then
    alter table public.whatsapp_messages
      add constraint fk_whatsapp_messages_workspace
      foreign key (workspace_id) references public.workspaces (id)
      on update cascade on delete restrict not valid;
    alter table public.whatsapp_messages validate constraint fk_whatsapp_messages_workspace;
  end if;
end $$;

do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema = 'public' and table_name = 'whatsapp_tasks'
  ) and not exists (
    select 1 from pg_constraint where conname = 'fk_whatsapp_tasks_workspace'
  ) then
    alter table public.whatsapp_tasks
      add constraint fk_whatsapp_tasks_workspace
      foreign key (workspace_id) references public.workspaces (id)
      on update cascade on delete restrict not valid;
    alter table public.whatsapp_tasks validate constraint fk_whatsapp_tasks_workspace;
  end if;
end $$;

do $$
begin
  if exists (
    select 1 from information_schema.tables
    where table_schema = 'public' and table_name = 'ai_state'
  ) and not exists (
    select 1 from pg_constraint where conname = 'fk_ai_state_workspace'
  ) then
    alter table public.ai_state
      add constraint fk_ai_state_workspace
      foreign key (workspace_id) references public.workspaces (id)
      on update cascade on delete restrict not valid;
    alter table public.ai_state validate constraint fk_ai_state_workspace;
  end if;
end $$;

commit;
