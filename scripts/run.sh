#!/usr/bin/env bash
# Atlas dashboard launcher. Builds the frontend if needed, then serves the app
# (frontend + API) on http://127.0.0.1:8787. Run with:  ./scripts/run.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${1:-8787}"

# ── Share the real profiles across git worktrees ─────────────────────────────
# profiles/ is gitignored (personal data, public repo), so a linked worktree starts with
# NO profiles — you'd see the onboarding wizard instead of your real accounts. When launched
# from a worktree, point Atlas at the MAIN checkout's profiles/ (a single source of truth,
# live) via $ATLAS_PROFILES_DIR. No-op in the main checkout, a plain clone, or when the var
# is already set. `git rev-parse --git-common-dir` resolves to the shared .git even from a
# worktree, so its parent is the main checkout root.
if [ -z "${ATLAS_PROFILES_DIR:-}" ]; then
  common_git="$(git rev-parse --git-common-dir 2>/dev/null || true)"
  if [ -n "$common_git" ]; then
    main_root="$(cd "$(dirname "$common_git")" && pwd)"
    if [ "$main_root" != "$PWD" ] && [ -f "$main_root/profiles/registry.json" ]; then
      export ATLAS_PROFILES_DIR="$main_root/profiles"
      echo "Worktree detectado → usando los perfiles reales de: $ATLAS_PROFILES_DIR"
    fi
  fi
fi

# One-time, idempotent migration of the legacy single-user layout into profiles/owner/.
# No-op once it has run. Keep a SINGLE uvicorn worker below — the active-profile pointer
# is process-global state, so multiple workers would diverge.
uv run atlas profiles init

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
