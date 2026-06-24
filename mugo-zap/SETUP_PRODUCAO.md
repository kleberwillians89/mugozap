# Setup de producao MugôZap

Este guia prepara o MugôZap para rodar com login real da equipe Mugô e permissoes por perfil.

## 1. Pre-requisitos

- Projeto Supabase criado e acessivel.
- Backend publicado ou pronto para rodar com as variaveis de ambiente de producao.
- Frontend publicado com a URL do backend configurada.
- WhatsApp Cloud API configurado no app da Meta.
- Acesso administrativo ao Supabase para aplicar SQL e criar usuarios Auth.

## 2. Aplicar migrations

Migration obrigatoria desta etapa:

```bash
supabase/migrations/20260624_profiles_permissions.sql
```

### Opcao A: Supabase SQL Editor

1. Abra o projeto no Supabase.
2. Acesse `SQL Editor`.
3. Cole o conteudo de `supabase/migrations/20260624_profiles_permissions.sql`.
4. Execute o SQL.
5. Confirme que a execucao terminou sem erro.

### Opcao B: Supabase CLI

Use esta opcao somente se o projeto estiver linkado neste clone.

```bash
supabase link --project-ref SEU_PROJECT_REF
supabase db push
```

### Opcao C: psql

Use esta opcao se tiver a connection string administrativa do banco.

```bash
psql "$DATABASE_URL" -f supabase/migrations/20260624_profiles_permissions.sql
```

## 3. Validar migration

Execute no SQL Editor do Supabase:

```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'profiles'
order by ordinal_position;
```

Campos esperados em `profiles`:

- `id`
- `auth_user_id`
- `workspace_id`
- `name`
- `email`
- `role`
- `active`
- `created_at`
- `updated_at`

Valide os campos de responsavel e status nas conversas:

```sql
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name in ('whatsapp_users', 'whatsapp_conversations')
  and column_name in ('status', 'owner', 'assigned_to', 'human_owner', 'closed_at')
order by table_name, column_name;
```

Valide que a tabela `profiles` esta com RLS ativo:

```sql
select relname, relrowsecurity
from pg_class
where relname = 'profiles';
```

Resultado esperado: `relrowsecurity = true`.

Observacao: o frontend nao deve consultar `profiles` diretamente com chave anonima. A gestao de usuarios passa pelo backend, que valida o usuario autenticado e usa `SUPABASE_SERVICE_ROLE_KEY` no servidor.

## 4. Variaveis de ambiente

### Backend

Configure no ambiente de producao:

```env
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_SERVICE_ROLE_KEY=service-role-key-segura
SUPABASE_ANON_KEY=anon-key-publica
SUPABASE_PROFILES_TABLE=profiles

DEFAULT_WORKSPACE_ID=workspace-mugo-default
DEFAULT_WORKSPACE_NAME=Mugo
DEFAULT_WORKSPACE_SLUG=mugo

PANEL_API_KEY=chave-operacional-temporaria-ou-interna
MUGO_INTELLIGENCE_WEBHOOK_SECRET=chave-forte-exclusiva-do-intelligence
MUGO_WELCOME_WEBHOOK_SECRET=chave-forte-exclusiva-do-welcome
VERIFY_TOKEN=token-webhook-whatsapp
ALLOW_ORIGIN=https://URL-DO-FRONTEND

WHATSAPP_TOKEN=token-meta-cloud-api
WHATSAPP_PHONE_NUMBER_ID=id-do-numero
WHATSAPP_GRAPH_VERSION=v20.0

OPENAI_API_KEY=chave-openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT=12
```

Importante:

- Nunca exponha `SUPABASE_SERVICE_ROLE_KEY` no frontend.
- `PANEL_API_KEY` deve ser forte e tratado como segredo. Se usado para bootstrap do primeiro Admin, remova ou troque depois.
- `MUGO_INTELLIGENCE_WEBHOOK_SECRET` deve ser diferente de outras chaves e compartilhado somente com o Mugô Intelligence.
- `MUGO_WELCOME_WEBHOOK_SECRET` deve ser diferente das demais chaves e compartilhado somente com o Mugô Welcome.
- `ALLOW_ORIGIN` deve apontar para a URL real do frontend em producao.

### Frontend

Configure no build/deploy do Vite:

```env
VITE_API_URL=https://URL-DO-BACKEND
VITE_SUPABASE_URL=https://SEU-PROJETO.supabase.co
VITE_SUPABASE_ANON_KEY=anon-key-publica
VITE_DEFAULT_WORKSPACE_ID=workspace-mugo-default
```

Evite usar `VITE_PANEL_KEY` em producao. Login real deve ser feito via Supabase Auth.

## 5. Criar primeiro Admin

Usuario inicial:

- Nome: `Kleber`
- Role: `admin`
- Active: `true`

Nao coloque senha fixa no codigo.

### Caminho recomendado

1. No Supabase, acesse `Authentication > Users`.
2. Crie ou convide o usuario do Kleber com o email real da Mugô.
3. Use invite/magic link ou defina uma senha temporaria pelo painel do Supabase e force troca pelo fluxo operacional escolhido.
4. Copie o `User UID` criado no Supabase Auth.
5. Rode no SQL Editor, trocando o email e o UUID:

```sql
insert into public.profiles (
  auth_user_id,
  workspace_id,
  name,
  email,
  role,
  active
) values (
  'UUID_DO_USUARIO_AUTH',
  'workspace-mugo-default',
  'Kleber',
  'email-real-da-mugo@dominio.com',
  'admin',
  true
)
on conflict (auth_user_id) do update set
  name = excluded.name,
  email = excluded.email,
  role = excluded.role,
  active = excluded.active,
  updated_at = timezone('utc', now());
```

Valide:

```sql
select id, auth_user_id, name, email, role, active
from public.profiles
where email = 'email-real-da-mugo@dominio.com';
```

### Caminho alternativo via API de bootstrap

Se o backend estiver rodando e `PANEL_API_KEY` estiver configurado, o primeiro Admin tambem pode ser criado pela API interna. Use senha somente via variavel local, nunca versionada:

```bash
export MUGO_ADMIN_EMAIL="email-real-da-mugo@dominio.com"
export MUGO_ADMIN_PASSWORD="senha-digitada-fora-do-codigo"
export PANEL_API_KEY="valor-configurado-no-backend"

curl -X POST "https://URL-DO-BACKEND/api/users" \
  -H "Content-Type: application/json" \
  -H "X-Panel-Key: $PANEL_API_KEY" \
  -d "{
    \"name\": \"Kleber\",
    \"email\": \"$MUGO_ADMIN_EMAIL\",
    \"password\": \"$MUGO_ADMIN_PASSWORD\",
    \"role\": \"admin\",
    \"active\": true
  }"
```

Depois do bootstrap, prefira remover, rotacionar ou restringir `PANEL_API_KEY`.

## 6. Rodar backend

Local/producao simples:

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Producao com worker ASGI:

```bash
gunicorn --worker-class uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000
```

Se o comando for executado da raiz do repo, ajuste o modulo:

```bash
gunicorn --worker-class uvicorn.workers.UvicornWorker server.app:app --bind 0.0.0.0:8000
```

## 7. Rodar frontend

Build de producao:

```bash
cd web
npm install
npm run lint
npm run build
```

Publique a pasta:

```bash
web/dist
```

## 8. Validar login

1. Acesse a URL do frontend.
2. Entre com o usuario do Kleber criado no Supabase Auth.
3. No topo do sistema, confirme:
   - nome do usuario
   - role `admin`
   - botao `Sair`
4. Abra `Configurações > Usuários`.
5. Confirme que a tela lista usuarios e permite criar/editar.

## 9. Validar permissoes

Crie tres usuarios de teste, um por perfil:

- Admin
- Gestor
- Atendimento

Validacoes esperadas:

- Admin:
  - ve todas as conversas
  - acessa `Configurações > Usuários`
  - cria/edita/desativa usuarios
  - altera responsavel
  - altera status
  - acessa cobrancas
  - acessa diagnostico
  - arquiva/remove conversa

- Gestor:
  - ve todas as conversas
  - altera responsavel
  - altera status
  - acessa cobrancas
  - acessa diagnostico
  - nao acessa gestao de usuarios
  - nao arquiva/remove conversa
  - nao pode listar/criar/editar usuarios via API ou UI

- Atendimento:
  - ve conversas sem responsavel
  - ve conversas atribuidas a si
  - nao ve conversa de outro atendente
  - pode assumir atendimento sem responsavel
  - pode alterar status das proprias conversas
  - acessa diagnostico e contatos
  - nao acessa cobrancas
  - nao acessa gestao de usuarios
  - nao arquiva/remove conversa

## 10. Validar webhook WhatsApp

No painel da Meta:

- Callback URL: `https://URL-DO-BACKEND/webhook`
- Verify token: mesmo valor de `VERIFY_TOKEN`
- Eventos: mensagens do WhatsApp Business Cloud API

Depois envie uma mensagem real para o numero conectado e confirme que a conversa aparece no Inbox.

## 11. Integrar Mugô Intelligence

Endpoint de recebimento:

```text
POST https://URL-DO-BACKEND/api/integrations/mugo-intelligence/lead
```

Header obrigatorio:

```text
X-Mugo-Webhook-Secret: valor-de-MUGO_INTELLIGENCE_WEBHOOK_SECRET
```

Payload esperado:

```json
{
  "lead_id": "lead_123",
  "nome": "Nome do lead",
  "empresa": "Empresa",
  "telefone": "+55 (11) 99999-9999",
  "email": "lead@empresa.com",
  "segmento": "Serviços",
  "instagram": "@empresa",
  "site": "https://empresa.com",
  "linkedin": "https://linkedin.com/company/empresa",
  "google_business": "https://g.page/empresa",
  "score_geral": 82,
  "score_marketing": 70,
  "score_vendas": 75,
  "score_automacao": 60,
  "score_dados": 55,
  "score_relacionamento": 80,
  "principal_oportunidade": "organizar captação e atendimento comercial",
  "servico_mugo_recomendado": "Automação comercial com WhatsApp",
  "resumo_gerado": "Lead tem boa demanda e precisa estruturar atendimento.",
  "respostas_completas": {
    "desafio": "perde leads por falta de acompanhamento"
  },
  "temperatura": "Quente",
  "origem_lead": "Mugô Intelligence",
  "utm_source": "site",
  "utm_medium": "diagnostico",
  "utm_campaign": "mugo-intelligence"
}
```

Teste com `curl`:

```bash
export MUGO_INTELLIGENCE_WEBHOOK_SECRET="valor-configurado-no-backend"

curl -X POST "https://URL-DO-BACKEND/api/integrations/mugo-intelligence/lead" \
  -H "Content-Type: application/json" \
  -H "X-Mugo-Webhook-Secret: $MUGO_INTELLIGENCE_WEBHOOK_SECRET" \
  -d '{
    "lead_id": "teste-001",
    "nome": "Lead Teste",
    "empresa": "Empresa Teste",
    "telefone": "+55 (11) 99999-9999",
    "email": "lead.teste@empresa.com",
    "segmento": "Serviços",
    "score_geral": 82,
    "score_marketing": 70,
    "score_vendas": 75,
    "score_automacao": 60,
    "score_dados": 55,
    "score_relacionamento": 80,
    "principal_oportunidade": "organizar captação e atendimento comercial",
    "servico_mugo_recomendado": "Automação comercial com WhatsApp",
    "resumo_gerado": "Lead teste com diagnóstico concluído.",
    "temperatura": "Quente",
    "origem_lead": "Mugô Intelligence",
    "utm_source": "site",
    "utm_medium": "diagnostico",
    "utm_campaign": "teste"
  }'
```

Resultado esperado:

- `ok = true`
- contato criado ou atualizado
- conversa vinculada pelo `wa_id` ou telefone, quando existir
- status `Diagnóstico concluído`
- diagnóstico visivel na tela Diagnóstico e no painel lateral
- evento `Diagnóstico Mugô Intelligence recebido` no histórico

## 12. Integrar Mugô Welcome

Endpoint de recebimento:

```text
POST https://URL-DO-BACKEND/api/integrations/mugo-welcome/lead
```

Header obrigatorio:

```text
X-Mugo-Welcome-Secret: valor-de-MUGO_WELCOME_WEBHOOK_SECRET
```

Payload esperado:

```json
{
  "lead_id": "welcome_123",
  "empresa": "Empresa do cliente",
  "responsavel": "Nome do responsável",
  "telefone": "+55 (11) 99999-9999",
  "email": "cliente@empresa.com",
  "cnpj": "00.000.000/0001-00",
  "site": "https://empresa.com",
  "instagram": "@empresa",
  "servicos": "Social media, tráfego e automação",
  "publico_alvo": "Empresas B2B",
  "diferenciais": "Atendimento consultivo",
  "objetivos": "Aumentar geração de leads qualificados",
  "metricas": "Leads, CAC e taxa de conversão",
  "tom_de_voz": "Consultivo e direto",
  "concorrentes": "Concorrente A, Concorrente B",
  "referencias": "https://referencia.com",
  "frequencia": "3 posts por semana",
  "desafios": "Falta de previsibilidade comercial",
  "orcamento": "R$ 5.000/mês",
  "prazo": "30 dias",
  "observacoes": "Cliente já usa WhatsApp comercial.",
  "origem_lead": "Mugô Welcome",
  "utm_source": "welcome",
  "utm_medium": "form",
  "utm_campaign": "onboarding"
}
```

Teste com `curl`:

```bash
export MUGO_WELCOME_WEBHOOK_SECRET="valor-configurado-no-backend"

curl -X POST "https://URL-DO-BACKEND/api/integrations/mugo-welcome/lead" \
  -H "Content-Type: application/json" \
  -H "X-Mugo-Welcome-Secret: $MUGO_WELCOME_WEBHOOK_SECRET" \
  -d '{
    "lead_id": "welcome-teste-001",
    "empresa": "Empresa Teste",
    "responsavel": "Lead Teste",
    "telefone": "+55 (11) 99999-9999",
    "email": "lead.teste@empresa.com",
    "site": "https://empresa-teste.com",
    "instagram": "@empresateste",
    "servicos": "Automação comercial com WhatsApp",
    "objetivos": "Responder leads mais rápido",
    "orcamento": "R$ 5.000/mês",
    "prazo": "30 dias",
    "observacoes": "Briefing teste recebido pelo Mugô Welcome.",
    "origem_lead": "Mugô Welcome",
    "utm_source": "welcome",
    "utm_medium": "form",
    "utm_campaign": "teste"
  }'
```

Resultado esperado:

- `ok = true`
- contato criado ou atualizado
- conversa vinculada pelo `wa_id` ou telefone, quando existir
- status `Briefing recebido`
- `automation_stage = welcome_completed`
- bloco `Briefing Welcome` visivel no painel lateral
- evento `Briefing Mugô Welcome recebido` no histórico

Erros esperados:

- `401`: secret ausente ou invalido.
- `400`: telefone ausente.
- `422`: payload invalido.

Observacoes operacionais:

- O webhook exige `X-Mugo-Webhook-Secret` valido; sem ele a resposta e `401`.
- Se o segredo nao estiver configurado no backend, o endpoint devolve `500` com mensagem explicita.
- Payloads invalidos ou sem telefone retornam `400`.
- Reenvios do webhook sao seguros: o endpoint atualiza a conversa existente pelo telefone/`wa_id` e preserva o ultimo diagnostico recebido.
- Acoes sensiveis de cobranca e gestao de usuarios continuam bloqueadas para perfis sem permissao, mesmo que o cliente tente chamar as APIs diretamente.

## 13. Checklist de producao

- [ ] Supabase configurado.
- [ ] Migration `20260624_profiles_permissions.sql` aplicada.
- [ ] Tabela `profiles` criada.
- [ ] RLS ativo em `profiles`.
- [ ] Campos `status`, `owner`, `assigned_to`, `human_owner`, `closed_at` criados em `whatsapp_users`.
- [ ] Campos `status`, `owner`, `assigned_to`, `human_owner`, `closed_at` criados em `whatsapp_conversations`.
- [ ] Usuario admin inicial `Kleber` criado no Supabase Auth.
- [ ] Profile do `Kleber` criado com `role = admin` e `active = true`.
- [ ] `SUPABASE_SERVICE_ROLE_KEY` configurada somente no backend.
- [ ] `VITE_SUPABASE_ANON_KEY` configurada somente com chave anonima.
- [ ] URL do frontend configurada em `ALLOW_ORIGIN`.
- [ ] URL do backend configurada em `VITE_API_URL`.
- [ ] WhatsApp webhook configurado.
- [ ] Webhook do Mugô Intelligence configurado.
- [ ] Webhook do Mugô Welcome configurado.
- [ ] `MUGO_INTELLIGENCE_WEBHOOK_SECRET` configurado no backend.
- [ ] `MUGO_WELCOME_WEBHOOK_SECRET` configurado no backend.
- [ ] Header `X-Mugo-Webhook-Secret` configurado no Mugô Intelligence.
- [ ] Header `X-Mugo-Welcome-Secret` configurado no Mugô Welcome.
- [ ] `WHATSAPP_TOKEN` configurado.
- [ ] `WHATSAPP_PHONE_NUMBER_ID` configurado.
- [ ] Variaveis de ambiente revisadas.
- [ ] `npm run lint` aprovado.
- [ ] `npm run build` aprovado.
- [ ] Backend validado com `python3 -m py_compile`.
- [ ] Login real validado.
- [ ] Permissoes por role validadas.
- [ ] Fluxo de assumir/transferir atendimento validado.
- [ ] Cobrancas bloqueadas para Atendimento.
- [ ] Gestao de usuarios bloqueada para Gestor e Atendimento.
- [ ] Arquivamento/remocao bloqueado para Gestor e Atendimento.
- [ ] Diagnóstico do Mugô Intelligence caindo automaticamente na conversa correta.
- [ ] Briefing do Mugô Welcome caindo automaticamente no bloco correto.

## 14. Comandos de validacao final

Execute da raiz do repo:

```bash
cd web
npm run lint
npm run build
```

Execute da raiz do repo:

```bash
python3 -m py_compile server/app.py server/services/profiles.py server/services/state.py server/services/central_attendance.py
```
