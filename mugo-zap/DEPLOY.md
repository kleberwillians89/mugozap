# Deploy Checklist

## Backend
- Runtime: `python-3.12.3` em `server/runtime.txt`
- Instalação: `pip install -r server/requirements.txt`
- Start command:
  ```bash
  gunicorn --worker-class uvicorn.workers.UvicornWorker server.app:app
  ```
- Defina os secrets do backend:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_ANON_KEY`
  - `WHATSAPP_TOKEN`
  - `WHATSAPP_PHONE_NUMBER_ID`
  - `VERIFY_TOKEN`
  - `PANEL_API_KEY`
  - `OPENAI_API_KEY`
  - `DEFAULT_WORKSPACE_ID`

## Frontend
- Build command:
  ```bash
  cd web && npm ci && npm run build
  ```
- Publique `web/dist/` em hosting estático.
- Defina no ambiente de build:
  - `VITE_API_URL`
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_PANEL_KEY`
  - `VITE_DEFAULT_WORKSPACE_ID`

## Banco / Supabase
- Rode as migrations em `supabase/migrations/`.
- Verifique a existência do workspace default da Mugô.
- Confirme políticas e permissões das tabelas usadas por:
  - `whatsapp_users`
  - `whatsapp_messages`
  - `whatsapp_tasks`
  - `ai_state`
  - `workspaces`

## Validação pós-deploy
- `GET /health` retorna `ok: true`
- Login no painel funciona
- SSE em `/events?token=...&workspace_id=...` conecta
- Webhook do WhatsApp responde em `/webhook`
- `npm run build` passa no frontend
