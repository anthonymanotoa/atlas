#!/usr/bin/env bash
# Atlas one-command health check — "is the repo green?" across both stacks.
# Syncs deps, runs the Python tests, then typechecks the dashboard frontend.
# Exits non-zero on the first failure. Run with:  ./scripts/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Python: uv sync (installs the dev dependency group)"
uv sync

echo "==> Python: tests"
uv run pytest

echo "==> Frontend: install + typecheck"
npm --prefix dashboard/frontend install
npm --prefix dashboard/frontend run typecheck

echo ""
echo "✓ All checks passed."
