# Security notes (dashboard frontend)

## The esbuild `npm audit` finding (3 high) — non-exploitable, dev-only

`npm audit` reports 3 high-severity issues in **esbuild** (pulled in by Vite). Context:

- **It's a build/dev dependency**, not shipped to anyone. The production output is static
  HTML/CSS/JS. Confirm with:
  ```bash
  npm --prefix dashboard/frontend run audit:prod   # → found 0 vulnerabilities
  ```
- **The advisory ([GHSA-gv7w-rqvm-qjhr](https://github.com/advisories/GHSA-gv7w-rqvm-qjhr))
  is a Deno-specific install vector** (`NPM_CONFIG_REGISTRY`). This project installs via
  npm/Node and the dashboard binds to `127.0.0.1` only — the vulnerable path is never used.
- **The fix is esbuild ≥ 0.28.1, which isn't yet available** in this environment's npm
  registry (it is date-restricted to versions published before 2026-06-06; 0.28.1 is newer).
  An `overrides` pin therefore can't be installed right now.

**When it becomes patchable** (registry advances past esbuild 0.28.1), clear it with:
```bash
# add to dashboard/frontend/package.json:  "overrides": { "esbuild": "^0.28.1" }
npm --prefix dashboard/frontend install   # then `npm audit` → 0
```
Or upgrade Vite to a release that bundles patched esbuild. Until then, the finding is
informational for this local, single-user tool.
