#!/usr/bin/env bash
set -e

ROOT="/Users/klebs/Desktop/mugozap"
SERVER="$ROOT/mugo-zap/server"
WEB="$ROOT/mugo-zap/web"

mkdir -p "$SERVER/services"
mkdir -p "$WEB"

echo "✅ Pastas criadas."

echo "⚠️ Agora, dentro de $SERVER:"
echo "   - Garanta que existe .venv e requirements.txt"
echo "   - Garanta que existe .env (com OPENAI_API_KEY etc.)"

echo ""
echo "✅ Próximo: criar frontend com Vite"
cd "$ROOT/mugo-zap"
npm create vite@latest web -- --template react >/dev/null
cd "$WEB"
npm install >/dev/null

echo "✅ Frontend Vite React criado em $WEB"
echo ""
echo "Próximo passo:"
echo "1) Rodar backend:"
echo "   cd $SERVER && source .venv/bin/activate && uvicorn app:app --reload --port 8000"
echo ""
echo "2) Rodar frontend:"
echo "   cd $WEB && npm run dev"
