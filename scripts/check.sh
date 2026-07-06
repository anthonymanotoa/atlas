#!/usr/bin/env bash
# Atlas one-command health check — "is the repo green?" across both stacks.
# Syncs deps, lints + tests Python, then lints/typechecks/tests the dashboard frontend.
# Exits non-zero on the first failure. Run with:  ./scripts/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Python: uv sync (installs the dev dependency group)"
uv sync

echo "==> Python: ruff lint + format check"
uv run ruff check .
uv run ruff format --check .

echo "==> Python: tests"
uv run pytest

echo "==> Frontend: install"
npm --prefix dashboard/frontend install

echo "==> Frontend: lint + format check + typecheck + tests"
npm --prefix dashboard/frontend run lint
npm --prefix dashboard/frontend run format:check
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test

echo "==> Frontend: production build"
npm --prefix dashboard/frontend run build

echo ""
echo "✓ All checks passed."
