#!/usr/bin/env bash
# Linux / macOS setup (Windows users: scripts/setup.ps1)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements-dev.txt
[ -f .env ] || cp .env.example .env
backend/.venv/bin/python scripts/download_weights.py || echo "weights download failed - see README"
(cd frontend && npm install)
echo "Done. Backend: (cd backend && .venv/bin/uvicorn app.main:app --reload)   Frontend: (cd frontend && npm run dev)"
