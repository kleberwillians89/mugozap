# Painel Mugozap

Frontend React/Vite do painel interno.

## Estabilidade de build
O projeto usa o `vite` oficial, sem alias para `rolldown-vite`, para evitar fragilidade em CI/CD e diferenças de bindings nativos entre ambientes.

## Setup
```bash
cp .env.example .env
npm install
npm run dev
```

## Variáveis
- `VITE_API_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_PANEL_KEY`
- `VITE_DEFAULT_WORKSPACE_ID`

## Scripts
- `npm run dev`
- `npm run build`
- `npm run lint`
- `npm run preview`

## Produção
Para CI/CD prefira:
```bash
npm ci
npm run build
```

Ambiente recomendado:
- Node 20 ou 22
- npm 10+
