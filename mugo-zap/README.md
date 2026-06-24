# Mugozap

Monorepo com backend FastAPI e frontend React/Vite para operação do painel interno da Mugô no WhatsApp.

## Estrutura
- `server/`: API FastAPI, integrações com WhatsApp, OpenAI e Supabase.
- `web/`: painel React/Vite autenticado com Supabase.
- `supabase/migrations/`: migrations SQL versionadas do banco.

## Setup local
Pré-requisitos:
- Python 3.12
- Node.js 20+
- npm 10+

Opção rápida:
```bash
./bootstrap.sh
```

Opção manual:
```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --port 8000
```

Em outro terminal:
```bash
cd web
cp .env.example .env
npm install
npm run dev
```

## Variáveis de ambiente
- Backend: use [`.env.example`](/Users/klebs/Desktop/mugozap/mugo-zap/.env.example) como referência principal ou copie [`.env.example`](/Users/klebs/Desktop/mugozap/mugo-zap/server/.env.example) em `server/.env`.
- Frontend: copie [`.env.example`](/Users/klebs/Desktop/mugozap/mugo-zap/web/.env.example) para `web/.env`.

As variáveis mais importantes são:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `WHATSAPP_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `OPENAI_API_KEY`
- `PANEL_API_KEY`
- `DEFAULT_WORKSPACE_ID`

## Comandos úteis
- Backend local: `cd server && source .venv/bin/activate && uvicorn app:app --reload --port 8000`
- Frontend local: `cd web && npm run dev`
- Build frontend: `cd web && npm run build`
- Verificação simples backend: `python3 -m py_compile server/app.py server/services/*.py`

## Deploy
- Backend: `gunicorn --worker-class uvicorn.workers.UvicornWorker server.app:app`
- Frontend: `cd web && npm run build`

Checklist detalhado em [DEPLOY.md](/Users/klebs/Desktop/mugozap/mugo-zap/DEPLOY.md).

Setup de producao com multiusuario em [SETUP_PRODUCAO.md](SETUP_PRODUCAO.md).
