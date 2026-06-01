#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$ROOT/mugo-zap"
SERVER="$APP_ROOT/server"
WEB="$APP_ROOT/web"

if [[ ! -d "$SERVER" || ! -d "$WEB" ]]; then
  echo "Estrutura esperada não encontrada em $APP_ROOT" >&2
  exit 1
fi

echo "Preparando Mugozap em:"
echo "  app:    $APP_ROOT"
echo "  server: $SERVER"
echo "  web:    $WEB"
echo

if [[ ! -d "$SERVER/.venv" ]]; then
  python3 -m venv "$SERVER/.venv"
fi

"$SERVER/.venv/bin/pip" install --upgrade pip >/dev/null
"$SERVER/.venv/bin/pip" install -r "$SERVER/requirements.txt"

cd "$WEB"
npm install

echo
echo "Setup concluído."
echo
echo "Próximos passos:"
echo "1. Backend:"
echo "   cd $SERVER && cp .env.example .env && source .venv/bin/activate && uvicorn app:app --reload --port 8000"
echo
echo "2. Frontend:"
echo "   cd $WEB && cp .env.example .env && npm run dev"
