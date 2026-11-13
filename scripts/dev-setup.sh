#!/usr/bin/env bash
set -euo pipefail

echo "==> Pika local setup"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Backend
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env — edit DATABASE_URL and secrets."
fi

# Frontend
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
if [ ! -f .env ]; then
  cp .env.example .env
fi

echo ""
echo "Setup complete."
echo "  Backend:  cd backend && source .venv/bin/activate && python run.py"
echo "  Worker:   cd backend && source .venv/bin/activate && celery -A celery_worker.celery worker -l info"
echo "  Frontend: cd frontend && npm run dev"
echo "  Or:       docker compose up --build"
