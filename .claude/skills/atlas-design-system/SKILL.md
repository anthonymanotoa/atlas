---
name: atlas-design-system
description: >-
  Apply the Atlas Design System v2 to ANY visual/UI work in this repo
  (the dashboard/frontend React app). ALWAYS use this whenever building, creating, making,
  designing, styling, restyling, or tweaking a component, page, screen, dashboard, board,
  card, modal/dialog, form, button, badge, chip, table, chart, tooltip, menu, toast, sidebar,
  or any UI — and whenever editing dashboard/frontend/src/**, src/components/ui/**,
  src/pages/**, src/hooks/**, or src/index.css. Ensures every change is brand-consistent
  (v2 OKLCH tokens, the shared primitives, router/query architecture) without re-specifying
  colors or styles.
---

# Atlas Design System v2 (enforcement skill)

La spec canónica es **`dashboard/frontend/DESIGN_SYSTEM.md`** (v2) — leerla antes de cualquier
cambio visual. Los valores de paleta/tipografía provienen de
`docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md`. El sistema v1 "Warm Editorial"
está RETIRADO: no reintroducir su aurora ámbar/terracota ni el compat layer `--color-*`.

## Fuentes de verdad (leer / reusar — no reinventar)
- `dashboard/frontend/DESIGN_SYSTEM.md` — tokens, tipografía, motion, patrones, arquitectura v2.
- `dashboard/frontend/src/index.css` — el sistema de tokens (`@theme inline` + `[data-theme]`).
- `dashboard/frontend/src/components/ui/*` — los primitivos + `states.tsx`
  (LoadingState/ErrorState/EmptyState). Componer desde aquí; no hacer equivalentes a mano.
- `dashboard/frontend/src/components/ui/icons.ts` — único lugar de iconos de dominio. Sin emoji.
- `dashboard/frontend/src/hooks/` — capa de datos TanStack Query (keys en `hooks/keys.ts`).
- `dashboard/frontend/src/routes.tsx` + `src/components/AppShell.tsx` — navegación y shell.

## Reglas no negociables
1. Tokens semánticos / utilities (`bg-card`, `text-muted-foreground`, `border-border`,
   `bg-primary`, `bg-secondary`, `bg-success/warning/info/destructive`, `bg-sidebar*`,
   `ring-ring`) o `var(--token)`. Nunca hex ni colores crudos.
2. Nunca `bg-accent` / `text-accent-foreground` / `bg-muted` (sin mapear a propósito).
3. Tema = `data-theme` en `<html>` (hook `useTheme`). Nunca la clase `.dark`.
4. Vistas nuevas = ruta en `src/routes.tsx` + página en `src/pages/` + datos vía hooks de
   `src/hooks/` (TanStack Query). Prohibido fetch manual con useEffect en páginas.
5. Estados de página SIEMPRE con `LoadingState`/`ErrorState`/`EmptyState`; feedback con sonner
   (`toast.loading`+`id` en operaciones largas; `Deshacer` en acciones destructivas).
6. Tipografía: `text-display/h1/h2/h3/caption`, `font-mono` para código/paths, `tabular-nums`
   en números vivos. Sin emoji crudo: `ui/icons.ts`.
7. `cn` desde `@/lib/utils`; `@/` → `src/`.
8. Motion: `--ease-*`/`--dur-*` + tw-animate-css; respetar `prefers-reduced-motion`; nunca
   animar nodos dnd-kit arrastrados ni `backdrop-filter` en ancestros draggables.

## Invariantes
- **Solo visual** salvo que la tarea sea explícitamente de lógica — no tocar handlers,
  `src/api.ts`, hooks de datos, props ni flujo de estado.
- Strings de usuario en **español** (varios fijados por tests).
- Lint `--max-warnings 0`; el build es aparte de check.sh.

## Tras cualquier cambio de UI, verificar
```bash
npm --prefix dashboard/frontend run lint
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
```

Añadir un componente shadcn está bien (`components.json` sigue configurado), pero re-tematizarlo
a los tokens v2 y **revertir cualquier edición de la CLI a `src/index.css`**.
