#!/usr/bin/env bash
# Atlas dashboard launcher. Builds the frontend if needed, then serves the app
# (frontend + API) on http://127.0.0.1:8787. Run with:  ./scripts/run.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${1:-8787}"

if [ ! -f dashboard/frontend/dist/index.html ]; then
  echo "Building dashboard frontend..."
  npm --prefix dashboard/frontend install
  npm --prefix dashboard/frontend run build
fi

echo ""
echo "Atlas dashboard → http://127.0.0.1:${PORT}"
echo "(Ctrl+C para detener)"
echo ""
exec uv run uvicorn dashboard.backend.main:app --host 127.0.0.1 --port "${PORT}"
