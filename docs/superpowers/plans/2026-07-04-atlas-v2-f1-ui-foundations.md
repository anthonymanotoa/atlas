# Atlas v2 — Fase 1: Fundaciones UI/UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el sistema de diseño "Warm Editorial" por el sistema v2 y re-arquitecturar el dashboard como app multi-vista (react-router v7 + TanStack Query v5) con paridad funcional total.

**Architecture:** El SPA pasa de un `App.tsx` monolito (useState + `load()`) a: tokens OKLCH semánticos v2 en `index.css` → primitivos `ui/` restyleados (mismas APIs) → capa de datos en `src/hooks/` (TanStack Query) → router con app shell (sidebar + header) y páginas en `src/pages/`. El detalle de job pasa de Sheet (DetailDrawer) a página `/jobs/:id` con tabs. FastAPI gana un catch-all SPA para que las URLs profundas funcionen servidas por `scripts/run.sh`.

**Tech Stack:** React 19, Vite 6, Tailwind v4 (`@theme inline`), Radix/shadcn-style primitives, dnd-kit, sonner, **react-router v7 (modo librería, paquete `react-router`)**, **@tanstack/react-query v5**, Vitest + Testing Library, FastAPI + SQLite (backend solo se toca para el SPA fallback).

## Global Constraints

- **Router:** react-router **v7 en modo librería** — paquete `react-router`, NUNCA `react-router-dom`. Imports: `import { createBrowserRouter, RouterProvider, NavLink, Outlet, useNavigate, useParams, Navigate, createMemoryRouter } from "react-router"`.
- **Data layer:** `@tanstack/react-query` v5. Toda lectura de API en páginas/shell pasa por hooks de `src/hooks/` — prohibido `useState` + `useEffect` + `api.*` para datos de servidor en páginas nuevas. (Los componentes hoja preexistentes `InterviewPanel`, `SocialSearch`, `PortfolioViewer` conservan su fetch interno: paridad, no purismo.)
- **Tests frontend:** `npm --prefix dashboard/frontend test` (vitest). Un archivo: `npm --prefix dashboard/frontend test -- <ruta>`.
- **Tests backend:** `rtk uv run --group dev pytest` (NUNCA pytest crudo; NUNCA `--extra dev`).
- **Lint/format/typecheck:** `npm --prefix dashboard/frontend run lint` es `--max-warnings 0`; correr también `run format` (prettier) y `run typecheck` antes de cada commit de frontend.
- **Commits:** SIEMPRE `git add <archivo1> <archivo2>` por nombre — nunca `git add .` ni `-A`. Todo mensaje de commit termina con la línea: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Repo público:** nada de datos personales (nombres, emails, empresas reales del usuario) en código, tests, fixtures o docs. Los datos reales viven solo en SQLite/`profiles/` gitignorados.
- **No romper el build servido por FastAPI:** `scripts/run.sh` sirve `dashboard/frontend/dist/` desde el backend en `127.0.0.1:8787`. La Task 4 (SPA fallback) es prerrequisito de que las rutas profundas funcionen ahí.
- **Tema:** mecanismo `data-theme="dark|light"` en `<html>` + `@custom-variant dark` — NUNCA introducir la clase `.dark` de shadcn.
- **Strings de UI en español** (varios están fijados por tests: `Todo al día`, `Acciones para hoy`, `Descartar`, `Re-preparar`, `Marcar como aplicado`).
- **Primitivos:** los 22 archivos de `src/components/ui/` conservan sus APIs exportadas (mismos nombres de componentes, variants y props). Restyle = clases/tokens, no firmas.
- **Excepción declarada de valores visuales (única permitida):** los VALORES OKLCH de paleta, tipografía (familias/pesos) y sombras vienen de `docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md` (propuesta visual aprobada aparte). Las tasks que los consumen lo declaran en **Consumes** y marcan cada valor con `/* ← visual-language doc */`. La ESTRUCTURA de tokens (nombres semánticos, `@theme inline`, `data-theme`) está completa en este plan.
- **Dependencias nuevas permitidas:** solo `react-router@^7`, `@tanstack/react-query@^5` y los paquetes de fuentes que nombre el visual-language doc. Nada más.
- Restricción dura de la spec: el resultado debe ser **distinto del Warm Editorial actual** (nada de aurora ámbar/terracota); el gate de mockups ya aprobó la dirección antes de ejecutar este plan.

---

## File Structure

**Frontend — crear:**

| Archivo | Responsabilidad |
| --- | --- |
| `dashboard/frontend/src/lib/queryClient.ts` | Instancia única de `QueryClient` con defaults (staleTime, retry). |
| `dashboard/frontend/src/hooks/keys.ts` | `qk` — factory central de query keys (una convención, cero strings sueltos). |
| `dashboard/frontend/src/hooks/useOverview.ts` | `useOverview(enabled?)` — `/api/overview` (overview + needs_action). |
| `dashboard/frontend/src/hooks/useBoard.ts` | `useBoard(enabled?)`, `useSetJobState()` (mutación con move optimista + rollback), tipo `BoardData`. |
| `dashboard/frontend/src/hooks/useJob.ts` | `useJob(id?)`, `usePrepJob()`, `useMarkApplied()`, `useRecordOutcome()`. |
| `dashboard/frontend/src/hooks/useProfiles.ts` | `useProfiles()`, `useSwitchProfile()`, `useRenameProfile()`. |
| `dashboard/frontend/src/hooks/useOnboarding.ts` | `useOnboarding()`, `useCompleteOnboarding()`. |
| `dashboard/frontend/src/hooks/useSettings.ts` | `useSettings()`, `useSetSetting()`, `useCsvColumns()`, `useCvLibrary()`. |
| `dashboard/frontend/src/hooks/usePortfolio.ts` | `usePortfolioLatest()`, `usePeers()`, `usePortfolioResearch()`, `useGeneratePortfolio()`, `useAddPeer()`. |
| `dashboard/frontend/src/hooks/useDiscover.ts` | `useDiscover(ov?)` — buscar ahora: dispara discover, pollea status, invalida todo; expone `{ searching, seconds, run }` + `searchSourcesLabel()`. |
| `dashboard/frontend/src/hooks/useTheme.ts` | `useTheme()` — data-theme + localStorage `atlas-theme`. |
| `dashboard/frontend/src/hooks/hooks.test.tsx` | Tests de la capa de datos (query + mutación optimista + rollback). |
| `dashboard/frontend/src/test/utils.tsx` | `renderWithQuery()` y (desde Task 5) `renderRoutes()` — helpers de test con providers. |
| `dashboard/frontend/src/routes.tsx` | `routes: RouteObject[]` — árbol de rutas (exportado plano para poder testear con `createMemoryRouter`). |
| `dashboard/frontend/src/components/AppShell.tsx` | Layout raíz: sidebar de navegación + header (perfil, Buscar, ⌘K, tema, refresh) + guard de onboarding + Toaster + diálogos globales + CommandPalette. |
| `dashboard/frontend/src/components/AppShell.test.tsx` | Tests del shell: redirect `/` → `/pipeline`, sidebar, guard de onboarding. |
| `dashboard/frontend/src/pages/PipelinePage.tsx` | Vista kanban: NeedsAction + FilterBar + Board + descartadas + banner downtime. |
| `dashboard/frontend/src/pages/PipelinePage.test.tsx` | Tests de la página (render, dismiss con undo, error state). |
| `dashboard/frontend/src/pages/JobDetailPage.tsx` | Página `/jobs/:id` con tabs Resumen/CV/Mensajes/Entrevistas/Research + acciones (reemplaza DetailDrawer). |
| `dashboard/frontend/src/pages/JobDetailPage.test.tsx` | Migración de `DetailDrawer.test.tsx` + tabs + transparencia de score. |
| `dashboard/frontend/src/pages/AnalyticsPage.tsx` | Página `/analytics`: AnalyticsStrip (métricas + embudo). |
| `dashboard/frontend/src/pages/PortfolioPage.tsx` | Página `/portfolio`: PortfolioViewer keyed por perfil activo. |
| `dashboard/frontend/src/pages/SettingsPage.tsx` | Página `/settings` (absorbe SettingsModal: perfil, carpeta descargas, carpeta CVs, diseño CSV + export). |
| `dashboard/frontend/src/pages/SettingsPage.test.tsx` | Tests de settings como página. |
| `dashboard/frontend/src/pages/OnboardingPage.tsx` | Página `/onboarding`: envuelve OnboardingGate con hooks. |
| `dashboard/frontend/src/components/job-detail/SectionTitle.tsx` | Título de sección compartido del detalle. |
| `dashboard/frontend/src/components/job-detail/Ledger.tsx` | Checklist CV/mensajes/listo (extraído de DetailDrawer). |
| `dashboard/frontend/src/components/job-detail/MessageCard.tsx` | Card de mensaje + copiar/marcar enviado + `KIND_ES` (extraído). |
| `dashboard/frontend/src/components/job-detail/SocialSearch.tsx` | Señal social supervisada (extraído). |
| `dashboard/frontend/src/components/job-detail/RecordOutcome.tsx` | Registro de resultado humano (extraído). |
| `dashboard/frontend/src/components/job-detail/CompanyInsights.tsx` | Learnings por empresa (extraído). |
| `dashboard/frontend/src/components/job-detail/JobOverview.tsx` | "Sobre el puesto" + InfoItem (extraído). |
| `dashboard/frontend/src/components/job-detail/ScoreBreakdown.tsx` | **Nuevo** — transparencia de score: "Por qué N" con `fit_reasons` + `knockout_flags`. |
| `dashboard/frontend/src/components/job-detail/ScoreBreakdown.test.tsx` | Tests del desglose. |
| `dashboard/frontend/src/components/ui/states.tsx` | `LoadingState` / `ErrorState` / `EmptyState` compartidos. |
| `dashboard/frontend/src/components/ui/states.test.tsx` | Tests de los estados compartidos. |
| `dashboard/frontend/src/lib/lib.test.ts` | Test de `fitTone`/`ACTION_META` sobre tokens semánticos v2. |

**Frontend — modificar:**

| Archivo | Cambio |
| --- | --- |
| `dashboard/frontend/src/index.css` | Tokens v2 completos (valores del visual-language doc), sin compat layer legacy ni clases `.card/.chip/.btn`. |
| `dashboard/frontend/src/main.tsx` | Imports de fuentes v2 (paquetes del visual-language doc). |
| `dashboard/frontend/src/App.tsx` | Queda SOLO providers (`QueryClientProvider` + `TooltipProvider` + `RouterProvider`). |
| `dashboard/frontend/src/lib/index.ts` | `fitTone` y `ACTION_META` re-apuntados a tokens semánticos (`--success`, `--primary`, `--info`, `--warning`, `--accent2`, `--muted-foreground`). |
| `dashboard/frontend/src/components/ui/*.tsx` (22) | Restyle a v2 conservando APIs. |
| `dashboard/frontend/src/components/CommandPalette.tsx` | Grupo "Ir a" (rutas) + jobs navegan a `/jobs/:id`. |
| `dashboard/frontend/src/components/OnboardingGate.tsx` | Solo restyle del hero (gradiente Warm Editorial fuera); API intacta. |
| `dashboard/frontend/src/components/CvAuditDialog.tsx`, `HelpGuide.tsx`, `NeedsAction.tsx`, `AnalyticsStrip.tsx` | Solo re-apuntar `var(--color-*)` legacy a tokens v2 (sin cambiar comportamiento). |
| `dashboard/frontend/package.json` | + `react-router`, `@tanstack/react-query`, fuentes v2; − `@fontsource-variable/geist*` si el visual doc cambia la familia. |
| `dashboard/frontend/DESIGN_SYSTEM.md` | Reescrito como v2. |
| `.claude/skills/atlas-design-system/SKILL.md` | Actualizado al sistema v2 (deja de referenciar Warm Editorial). |

**Frontend — borrar (al final de su task):** `src/components/DetailDrawer.tsx`, `src/components/DetailDrawer.test.tsx` (migrado), `src/components/SettingsModal.tsx`.

**Backend — modificar:**

| Archivo | Cambio |
| --- | --- |
| `dashboard/backend/main.py:797-801` | Reemplazar `app.mount("/", StaticFiles(html=True))` por catch-all GET que sirve archivos de `dist/` y hace fallback a `index.html` (404 para `/api/*`). |
| `tests/test_backend_api.py` | + tests del SPA fallback. |

---

### Task 1: Tokens v2 en `index.css` + fuentes

**Files:**
- Modify: `dashboard/frontend/src/index.css` (reemplazo completo del archivo)
- Modify: `dashboard/frontend/src/main.tsx:3-4` (imports de fuentes)
- Modify: `dashboard/frontend/package.json` (dependencias de fuentes)

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md` — **única fuente de los valores OKLCH de paleta, familias tipográficas, sombras y radius.** Cada línea marcada `/* ← visual-language doc */` se copia literal de la tabla de tokens de ese doc. Si el doc no existe aún, PARAR y avisar al usuario (gate de mockups pendiente).
- Produces: los nombres de tokens que TODO el resto del plan usa:
  - Superficies: `--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`
  - Marca: `--primary`, `--primary-foreground`, `--accent2` (partner de gradientes/acentos secundarios)
  - Neutrales: `--secondary`, `--secondary-foreground`, `--muted-foreground`
  - Semánticos: `--success`, `--success-foreground`, `--warning`, `--warning-foreground`, `--info`, `--info-foreground`, `--destructive`, `--destructive-foreground`
  - Líneas/foco: `--border`, `--input`, `--ring`
  - Sidebar (nuevos, para el app shell): `--sidebar`, `--sidebar-foreground`, `--sidebar-border`, `--sidebar-active`, `--sidebar-active-foreground`
  - Charts: `--chart-1` … `--chart-5`
  - Elevación: `--shadow-xs|sm|md|lg`, `--highlight-top` (SIN `--shadow-glow`: era Warm Editorial; sus usos se eliminan en Tasks 2/5)
  - Motion: `--ease-out`, `--ease-in-out`, `--dur-fast|base|slow`
  - Radius: `--radius` (+ derivados `--radius-sm/md/lg/xl` en `@theme`)
  - Tipografía: `--font-sans`, `--font-mono`, escala `text-caption/h3/h2/h1/display`
  - Utilities Tailwind expuestas vía `@theme inline`: `bg-card`, `text-muted-foreground`, `border-border`, `bg-sidebar`, `text-sidebar-foreground`, `bg-sidebar-active`, etc. Igual que hoy, `accent`/`accent-foreground`/`muted` (superficie) NO se mapean.

- [ ] **Step 1: Verificar el gate de mockups**

Run: `ls docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md`
Expected: el archivo existe. Si no existe → PARAR la task y reportar "visual-language doc pendiente de aprobación".

- [ ] **Step 2: Instalar los paquetes de fuentes del visual doc**

El visual-language doc §Tipografía nombra los dos paquetes `@fontsource-variable/<sans>` y `@fontsource-variable/<mono>` (valores ← visual-language doc). Si mantiene Geist, saltar este step.

```bash
npm --prefix dashboard/frontend install @fontsource-variable/<sans-del-doc> @fontsource-variable/<mono-del-doc>
npm --prefix dashboard/frontend uninstall @fontsource-variable/geist @fontsource-variable/geist-mono
```

Y en `dashboard/frontend/src/main.tsx` reemplazar las líneas 3-4:

```tsx
import "@fontsource-variable/<sans-del-doc>";
import "@fontsource-variable/<mono-del-doc>";
```

- [ ] **Step 3: Reemplazar `src/index.css` completo con la estructura v2**

Estructura completa (los `oklch(…)` marcados se copian del visual-language doc; todo lo demás es literal):

```css
@import "tailwindcss";
@import "tw-animate-css";

/* ════════════════════════════════════════════════════════════════════════════
   Atlas — Design System v2
   Valores de paleta/tipografía/sombras: docs/superpowers/specs/
   2026-07-04-atlas-v2-visual-language.md (fuente única de verdad visual).
   Tema en runtime vía `data-theme="dark|light"` en <html> (useTheme + main.tsx).
   ──────────────────────────────────────────────────────────────────────────── */

@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

/* ── Tokens — dark (default) ──────────────────────────────────────────────── */
:root {
  --radius: /* ← visual-language doc */;

  --background: oklch(/* ← visual-language doc */);
  --foreground: oklch(/* ← visual-language doc */);
  --card: oklch(/* ← visual-language doc */);
  --card-foreground: oklch(/* ← visual-language doc */);
  --popover: oklch(/* ← visual-language doc */);
  --popover-foreground: oklch(/* ← visual-language doc */);

  --primary: oklch(/* ← visual-language doc */);
  --primary-foreground: oklch(/* ← visual-language doc */);
  --accent2: oklch(/* ← visual-language doc */);

  --secondary: oklch(/* ← visual-language doc */);
  --secondary-foreground: oklch(/* ← visual-language doc */);
  --muted-foreground: oklch(/* ← visual-language doc */);

  --success: oklch(/* ← visual-language doc */);
  --success-foreground: oklch(/* ← visual-language doc */);
  --warning: oklch(/* ← visual-language doc */);
  --warning-foreground: oklch(/* ← visual-language doc */);
  --info: oklch(/* ← visual-language doc */);
  --info-foreground: oklch(/* ← visual-language doc */);
  --destructive: oklch(/* ← visual-language doc */);
  --destructive-foreground: oklch(/* ← visual-language doc */);

  --border: oklch(/* ← visual-language doc */);
  --input: oklch(/* ← visual-language doc */);
  --ring: oklch(/* ← visual-language doc */);

  /* app shell v2 */
  --sidebar: oklch(/* ← visual-language doc */);
  --sidebar-foreground: oklch(/* ← visual-language doc */);
  --sidebar-border: oklch(/* ← visual-language doc */);
  --sidebar-active: oklch(/* ← visual-language doc */);
  --sidebar-active-foreground: oklch(/* ← visual-language doc */);

  --chart-1: oklch(/* ← visual-language doc */);
  --chart-2: oklch(/* ← visual-language doc */);
  --chart-3: oklch(/* ← visual-language doc */);
  --chart-4: oklch(/* ← visual-language doc */);
  --chart-5: oklch(/* ← visual-language doc */);

  --shadow-xs: /* ← visual-language doc */;
  --shadow-sm: /* ← visual-language doc */;
  --shadow-md: /* ← visual-language doc */;
  --shadow-lg: /* ← visual-language doc */;
  --highlight-top: /* ← visual-language doc */;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 120ms;
  --dur-base: 180ms;
  --dur-slow: 280ms;
}

/* ── Tokens — light ───────────────────────────────────────────────────────── */
:root[data-theme="light"] {
  /* MISMA lista de tokens de color/sombra que :root, con los valores de la
     columna "light" del visual-language doc. Copiar el bloque :root completo
     (desde --background hasta --highlight-top) y sustituir cada valor. */
}

:root,
:root[data-theme="dark"] {
  color-scheme: dark;
}
:root[data-theme="light"] {
  color-scheme: light;
}

/* ── Tailwind v4 theme map ────────────────────────────────────────────────────
   `accent`, `accent-foreground` y la superficie `muted` siguen SIN mapear a
   propósito (usar `secondary` para hovers y `text-muted-foreground` para texto
   apagado). Regla heredada de v1 que los primitivos ya cumplen. ── */
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted-foreground: var(--muted-foreground);
  --color-success: var(--success);
  --color-success-foreground: var(--success-foreground);
  --color-warning: var(--warning);
  --color-warning-foreground: var(--warning-foreground);
  --color-info: var(--info);
  --color-info-foreground: var(--info-foreground);
  --color-destructive: var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-active: var(--sidebar-active);
  --color-sidebar-active-foreground: var(--sidebar-active-foreground);
  --color-chart-1: var(--chart-1);
  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);
  --color-chart-4: var(--chart-4);
  --color-chart-5: var(--chart-5);

  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);

  --font-sans: /* ← visual-language doc */, ui-sans-serif, system-ui, sans-serif;
  --font-mono: /* ← visual-language doc */, ui-monospace, "SF Mono", Menlo, monospace;

  /* escala tipográfica — tamaños/pesos ← visual-language doc §Tipografía */
  --text-caption: /* ← visual-language doc */;
  --text-caption--line-height: /* ← visual-language doc */;
  --text-caption--letter-spacing: /* ← visual-language doc */;
  --text-caption--font-weight: /* ← visual-language doc */;
  --text-h3: /* ← visual-language doc */;
  --text-h3--line-height: /* ← visual-language doc */;
  --text-h3--font-weight: /* ← visual-language doc */;
  --text-h2: /* ← visual-language doc */;
  --text-h2--line-height: /* ← visual-language doc */;
  --text-h2--letter-spacing: /* ← visual-language doc */;
  --text-h2--font-weight: /* ← visual-language doc */;
  --text-h1: /* ← visual-language doc */;
  --text-h1--line-height: /* ← visual-language doc */;
  --text-h1--letter-spacing: /* ← visual-language doc */;
  --text-h1--font-weight: /* ← visual-language doc */;
  --text-display: /* ← visual-language doc */;
  --text-display--line-height: /* ← visual-language doc */;
  --text-display--letter-spacing: /* ← visual-language doc */;
  --text-display--font-weight: /* ← visual-language doc */;
}

/* ── Base ─────────────────────────────────────────────────────────────────── */
html,
body,
#root {
  height: 100%;
}

body {
  margin: 0;
  color: var(--foreground);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  /* fondo v2: lo que defina el visual-language doc §Canvas (NO la aurora
     ámbar/terracota de v1). Si el doc define un fondo plano, esto queda así: */
  background: var(--background);
}

::selection {
  background: color-mix(in oklch, var(--primary) 30%, transparent);
  color: var(--foreground);
}

* {
  border-color: var(--border);
}

:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 1px;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
::-webkit-scrollbar-thumb {
  background: color-mix(in oklch, var(--border) 80%, var(--foreground) 8%);
  border-radius: 8px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover {
  background: color-mix(in oklch, var(--border) 60%, var(--foreground) 18%);
  background-clip: padding-box;
}
::-webkit-scrollbar-track {
  background: transparent;
}

/* ── Motion ───────────────────────────────────────────────────────────────── */
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.fade-up {
  animation: fadeUp var(--dur-base) var(--ease-out) both;
}

@keyframes indet {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(360%);
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Notas de eliminación deliberada respecto a v1 (verificadas contra el código actual):
- Fuera el bloque `:root:root` de compat `--color-bg/panel/fg/faint/accent/done/pending/action/danger/muted` — la Task 2 migra sus 6 call sites reales (`lib/index.ts`, `AnalyticsStrip.tsx:76,85`, `OnboardingGate.tsx:126`, `DetailDrawer.tsx:669`, `CvAuditDialog.tsx:117`, `NeedsAction.tsx:35`) ANTES de que esto compile roto visualmente. **Orden dentro de la fase: Task 1 y Task 2 se commitean juntas solo si el preview intermedio molesta; si no, commit por task (los `var(--color-*)` sin definir solo degradan color, no rompen build).**
- Fuera `--shadow-glow` (usos actuales: `App.tsx:259`, `OnboardingGate.tsx:60`, `HelpGuide.tsx` — se limpian en Tasks 2 y 5).
- Fuera las clases legacy `.card`, `.chip`, `.btn`, `.btn-accent` (verificado por grep: cero usos en `src/**/*.tsx`).
- Fuera la aurora del `body` y su variante light.
- OJO regla v1 que sigue viva: **no escribir `*/` dentro de comentarios CSS** (p. ej. "bg-*/text-*" cierra el comentario).

- [ ] **Step 4: Typecheck + suite existente**

Run: `npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`
Expected: PASS (los tokens son CSS; nada de TS cambió salvo main.tsx imports).

- [ ] **Step 5: Build**

Run: `npm --prefix dashboard/frontend run build`
Expected: `vite build` termina con `✓ built in …` sin warnings de CSS.

- [ ] **Step 6: Commit**

```bash
git add dashboard/frontend/src/index.css dashboard/frontend/src/main.tsx dashboard/frontend/package.json dashboard/frontend/package-lock.json
git commit -m "feat(ui): design tokens v2 — nueva paleta OKLCH semántica light+dark

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Restyle de los 22 primitivos `ui/` + limpieza de tokens legacy

**Files:**
- Modify: `dashboard/frontend/src/lib/index.ts:33-45` (`ACTION_META`, `fitTone`)
- Test: `dashboard/frontend/src/lib/lib.test.ts` (crear)
- Modify: `dashboard/frontend/src/components/AnalyticsStrip.tsx:28,76,85`
- Modify: `dashboard/frontend/src/components/NeedsAction.tsx:35`
- Modify: `dashboard/frontend/src/components/OnboardingGate.tsx:59-63,123-128`
- Modify: `dashboard/frontend/src/components/DetailDrawer.tsx:666-670`
- Modify: `dashboard/frontend/src/components/CvAuditDialog.tsx:117`
- Modify: `dashboard/frontend/src/components/HelpGuide.tsx` (usos de `shadow-glow`/`accent2`/gradientes — localizar con grep en el step 6)
- Modify: `dashboard/frontend/src/components/ui/*.tsx` (los 22 — solo clases, cero cambios de API)

**Interfaces:**
- Consumes: tokens v2 de Task 1 (nombres exactos listados allí) + visual-language doc §Componentes (radius/sombras/detalles por primitivo).
- Produces:
  - `fitTone(score?: number | null): string` — MISMA firma; ahora devuelve `"var(--muted-foreground)" | "var(--success)" | "var(--primary)"`. Todo consumidor posterior (`ScoreRing`, `Badge variant="score"`, `JobDetailPage`) depende de que retorne un `var(--token)` v2 válido.
  - `ACTION_META: Record<string, { tone: string }>` con tonos `var(--accent2) | var(--info) | var(--success) | var(--warning)`.
  - Los 22 primitivos con APIs idénticas (verificado por typecheck + suite existente).

- [ ] **Step 1: Escribir el test que falla — `fitTone`/`ACTION_META` sin tokens legacy**

Crear `dashboard/frontend/src/lib/lib.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ACTION_META, fitTone } from "./index";

describe("fitTone (tokens v2)", () => {
  it("devuelve tokens semánticos v2, nunca el compat layer --color-*", () => {
    expect(fitTone(90)).toBe("var(--success)");
    expect(fitTone(70)).toBe("var(--primary)");
    expect(fitTone(40)).toBe("var(--muted-foreground)");
    expect(fitTone(null)).toBe("var(--muted-foreground)");
    expect(fitTone(undefined)).toBe("var(--muted-foreground)");
  });
});

describe("ACTION_META (tokens v2)", () => {
  it("cada tono es un var(--token) semántico, sin --color-*", () => {
    for (const meta of Object.values(ACTION_META)) {
      expect(meta.tone).toMatch(/^var\(--(accent2|info|success|warning)\)$/);
    }
  });
});
```

- [ ] **Step 2: Correrlo y verlo fallar**

Run: `npm --prefix dashboard/frontend test -- src/lib/lib.test.ts`
Expected: FAIL — `fitTone(90)` devuelve `"var(--color-done)"`.

- [ ] **Step 3: Migrar `lib/index.ts`**

Reemplazar las líneas 33-45 por:

```ts
// Tone per action type (the icon lives in components/ui/icons.ts).
export const ACTION_META: Record<string, { tone: string }> = {
  ask_referral: { tone: "var(--accent2)" },
  send_application: { tone: "var(--info)" },
  reply: { tone: "var(--success)" },
  follow_up: { tone: "var(--warning)" },
};

export function fitTone(score?: number | null): string {
  if (score == null) return "var(--muted-foreground)";
  if (score >= 85) return "var(--success)";
  if (score >= 65) return "var(--primary)";
  return "var(--muted-foreground)";
}
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `npm --prefix dashboard/frontend test -- src/lib/lib.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Migrar los 6 call sites del compat layer**

- `AnalyticsStrip.tsx:76`: `tone="var(--color-action)"` → `tone="var(--info)"`; línea 85: `tone="var(--color-done)"` → `tone="var(--success)"`; línea 28 (barra highlight): `style={{ background: "linear-gradient(90deg, var(--primary), var(--accent2))" }}` se conserva solo si el visual doc mantiene gradientes de marca; si no, `style={{ background: "var(--primary)" }}`.
- `NeedsAction.tsx:35`: fallback `{ tone: "var(--color-muted)" }` → `{ tone: "var(--muted-foreground)" }`.
- `OnboardingGate.tsx:126`, `DetailDrawer.tsx:669`, `CvAuditDialog.tsx:117`: `style={{ color: "var(--color-accent2)" }}` → `style={{ color: "var(--accent2)" }}`.
- `OnboardingGate.tsx:59-63` (hero con `shadow-[var(--shadow-glow)]` + gradiente + `before:` radial): reemplazar el `<div>` del logo por:

```tsx
<div className="mb-4 grid size-12 place-items-center rounded-2xl bg-primary text-lg font-bold text-primary-foreground shadow-[var(--shadow-md)]">
  A
</div>
```

- [ ] **Step 6: Barrer los usos restantes de Warm Editorial**

Run: `rtk proxy grep -rn 'shadow-glow\|--color-\(bg\|panel\|fg\|faint\|accent\|done\|pending\|action\|danger\|muted\)' dashboard/frontend/src --include='*.tsx' --include='*.ts'`
Expected tras editar: **cero matches** fuera de `App.tsx` (el logo del header de `App.tsx:259-263` muere entero en Task 5, se deja). `HelpGuide.tsx` y cualquier otro hit: aplicar la misma sustitución del Step 5 (gradiente/glow → `bg-primary` + `shadow-[var(--shadow-md)]`, `var(--color-accent2)` → `var(--accent2)`).

- [ ] **Step 7: Restyle de los 22 primitivos**

Para cada archivo de `src/components/ui/`, aplicar el visual-language doc §Componentes **sin tocar exports, variants ni props**. Los primitivos ya componen sobre tokens semánticos, así que el grueso del restyle vino gratis con Task 1; este step ajusta lo que el doc especifique distinto (radius por control, grosor de bordes, tratamiento hover, sombras). Checklist archivo por archivo (marcar aunque el cambio sea "nada que ajustar"):

`badge.tsx` · `button.tsx` · `card.tsx` · `checkbox.tsx` · `command.tsx` · `dialog.tsx` · `dropdown-menu.tsx` · `icons.ts` · `input.tsx` · `kbd.tsx` · `label.tsx` · `score-ring.tsx` · `scroll-area.tsx` · `select.tsx` · `separator.tsx` · `sheet.tsx` · `skeleton.tsx` · `sonner.tsx` · `switch.tsx` · `tabs.tsx` · `textarea.tsx` · `tooltip.tsx`

Reglas duras del restyle:
- Las cadenas de clases solo pueden referenciar utilities de tokens v2 (`bg-card`, `border-border`, `ring-ring`, `bg-sidebar`…) o `var(--token)`; nunca `bg-accent`/`bg-muted`/hex.
- `Button`: conservar variants `default/secondary/outline/ghost/destructive/link` y sizes `sm/default/lg/icon/icon-sm` (los usan 12+ componentes).
- `Badge`: conservar variants `default/secondary/outline/success/warning/info/destructive/score` (el `score` sigue leyendo `--tone` por style).
- `Select`: mantener contenido `z-[95]` y `position="popper"` (regla v1 que sigue: item value nunca `""`).
- No animar nodos arrastrados por dnd-kit ni meter `backdrop-filter` en ancestros draggables.

- [ ] **Step 8: Verificación completa frontend**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`
Expected: todo PASS; la suite existente (api, Board, NeedsAction, DetailDrawer) sigue verde — prueba de que las APIs de primitivos no cambiaron.

- [ ] **Step 9: QA visual rápido (preview tools)**

Arrancar backend + `npm --prefix dashboard/frontend run dev` (preview_start con launch.json apuntando a `npm run dev` en `dashboard/frontend`, puerto 5173) y verificar con preview_screenshot + preview_inspect: board, drawer, palette y settings en **ambos temas** (`document.documentElement.dataset.theme = 'light'` vía preview_eval). Nada debe verse ámbar/terracota v1.

- [ ] **Step 10: Commit**

```bash
git add dashboard/frontend/src/lib/index.ts dashboard/frontend/src/lib/lib.test.ts dashboard/frontend/src/components/ui dashboard/frontend/src/components/AnalyticsStrip.tsx dashboard/frontend/src/components/NeedsAction.tsx dashboard/frontend/src/components/OnboardingGate.tsx dashboard/frontend/src/components/DetailDrawer.tsx dashboard/frontend/src/components/CvAuditDialog.tsx dashboard/frontend/src/components/HelpGuide.tsx
git commit -m "feat(ui): restyle de primitivos a v2 y retiro del compat layer Warm Editorial

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Capa de datos — TanStack Query (hooks por recurso)

**Files:**
- Create: `dashboard/frontend/src/lib/queryClient.ts`
- Create: `dashboard/frontend/src/hooks/keys.ts`
- Create: `dashboard/frontend/src/hooks/useOverview.ts`
- Create: `dashboard/frontend/src/hooks/useBoard.ts`
- Create: `dashboard/frontend/src/hooks/useJob.ts`
- Create: `dashboard/frontend/src/hooks/useProfiles.ts`
- Create: `dashboard/frontend/src/hooks/useOnboarding.ts`
- Create: `dashboard/frontend/src/hooks/useSettings.ts`
- Create: `dashboard/frontend/src/hooks/usePortfolio.ts`
- Create: `dashboard/frontend/src/hooks/useDiscover.ts`
- Create: `dashboard/frontend/src/test/utils.tsx`
- Test: `dashboard/frontend/src/hooks/hooks.test.tsx`

**Interfaces:**
- Consumes: `api` y sus tipos de `src/api.ts` (sin cambios): `api.overview/board/job/setState/markApplied/prep/recordOutcome/profiles/switchProfile/renameProfile/onboarding/completeOnboarding/settings/setSetting/csvColumns/cvLibrary/portfolioLatest/peers/portfolioResearch/generatePortfolio/addPeer/discover/discoverStatus/brief`.
- Produces (firmas exactas — TODO el shell y las páginas dependen de esto):

```ts
// src/lib/queryClient.ts
export const queryClient: QueryClient;

// src/hooks/keys.ts
export const qk: {
  overview: readonly ["overview"];
  board: readonly ["board"];
  job: (id: string) => readonly ["job", string];
  profiles: readonly ["profiles"];
  onboarding: readonly ["onboarding"];
  settings: readonly ["settings"];
  csvColumns: readonly ["csv-columns"];
  cvLibrary: readonly ["cv-library"];
  portfolio: readonly ["portfolio"];
  peers: readonly ["peers"];
  portfolioResearch: readonly ["portfolio-research"];
};

// src/hooks/useOverview.ts
export function useOverview(enabled?: boolean): UseQueryResult<{ overview: Overview; needs_action: Action[] }, Error>;

// src/hooks/useBoard.ts
export type BoardData = { columns: string[]; jobs: Record<string, Job[]>; dismissed: Job[] };
export function useBoard(enabled?: boolean): UseQueryResult<BoardData, Error>;
export function useSetJobState(): UseMutationResult<unknown, Error, { id: string; state: string }, { prev?: BoardData }>;

// src/hooks/useJob.ts
export function useJob(id?: string): UseQueryResult<JobDetail, Error>;
export function usePrepJob(): UseMutationResult<{ ok: boolean; coverage: number; parse_ok: boolean; language: string }, Error, { id: string; language?: string }>;
export function useMarkApplied(): UseMutationResult<unknown, Error, string>;
export function useRecordOutcome(): UseMutationResult<{ ok: boolean; learnings: Learning[] }, Error, { id: string; body: Parameters<typeof api.recordOutcome>[1] }>;

// src/hooks/useProfiles.ts
export function useProfiles(): UseQueryResult<{ profiles: Profile[]; active: string }, Error>;
export function useSwitchProfile(): UseMutationResult<{ ok: boolean; active: string }, Error, string>;
export function useRenameProfile(): UseMutationResult<{ ok: boolean; id: string; label: string }, Error, { id: string; label: string }>;

// src/hooks/useOnboarding.ts
export function useOnboarding(): UseQueryResult<OnboardingStatus, Error>;
export function useCompleteOnboarding(): UseMutationResult<{ ok: boolean }, Error, void>;

// src/hooks/useSettings.ts
export function useSettings(enabled?: boolean): UseQueryResult<Record<string, string | null>, Error>;
export function useSetSetting(): UseMutationResult<{ ok: boolean; key: string; value: string }, Error, { key: string; value: string }>;
export function useCsvColumns(enabled?: boolean): UseQueryResult<{ available: CsvColumn[]; selected: string[] }, Error>;
export function useCvLibrary(enabled?: boolean): UseQueryResult<{ dir: string; count: number; files: { name: string; size: number; modified: number }[] }, Error>;

// src/hooks/usePortfolio.ts
export function usePortfolioLatest(): UseQueryResult<{ portfolio: Portfolio | null }, Error>;
export function usePeers(): UseQueryResult<{ peers: Peer[] }, Error>;
export function usePortfolioResearch(): UseQueryResult<PortfolioResearch, Error>;
export function useGeneratePortfolio(): UseMutationResult<{ ok: boolean; id: number; version: string; path: string }, Error, boolean>;
export function useAddPeer(): UseMutationResult<{ ok: boolean; id: number }, Error, Partial<Peer>>;

// src/hooks/useDiscover.ts
export function searchSourcesLabel(ov?: Overview | null): string;
export function useDiscover(ov?: Overview | null): { searching: boolean; seconds: number; run: () => Promise<void> };

// src/test/utils.tsx
export function makeQueryClient(): QueryClient; // retry:false, gcTime:Infinity — para tests
export function renderWithQuery(ui: React.ReactElement): ReturnType<typeof render>;
```

- [ ] **Step 1: Instalar TanStack Query**

```bash
npm --prefix dashboard/frontend install @tanstack/react-query@^5
```

- [ ] **Step 2: Escribir los tests que fallan**

Crear `dashboard/frontend/src/hooks/hooks.test.tsx`:

```tsx
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    board: vi.fn(),
    setState: vi.fn(),
    overview: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { makeQueryClient } from "../test/utils";
import { qk } from "./keys";
import { useBoard, useSetJobState, type BoardData } from "./useBoard";

const board: BoardData = {
  columns: ["shortlisted", "applied"],
  jobs: {
    shortlisted: [{ id: "j1", title: "DS", company: "Acme", state: "shortlisted" }],
    applied: [],
  },
  dismissed: [],
};

function wrapperFor(qc: ReturnType<typeof makeQueryClient>) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useBoard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carga el tablero desde /api/board", async () => {
    api.board.mockResolvedValue(board);
    const qc = makeQueryClient();
    const { result } = renderHook(() => useBoard(), { wrapper: wrapperFor(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.columns).toEqual(["shortlisted", "applied"]);
    expect(api.board).toHaveBeenCalledTimes(1);
  });

  it("enabled=false no dispara la request (gate de onboarding)", async () => {
    const qc = makeQueryClient();
    renderHook(() => useBoard(false), { wrapper: wrapperFor(qc) });
    await new Promise((r) => setTimeout(r, 20));
    expect(api.board).not.toHaveBeenCalled();
  });
});

describe("useSetJobState", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mueve el job en cache de forma optimista antes de resolver", async () => {
    api.setState.mockImplementation(() => new Promise(() => {})); // nunca resuelve
    const qc = makeQueryClient();
    qc.setQueryData(qk.board, board);
    const { result } = renderHook(() => useSetJobState(), { wrapper: wrapperFor(qc) });
    result.current.mutate({ id: "j1", state: "applied" });
    await waitFor(() => {
      const data = qc.getQueryData<BoardData>(qk.board);
      expect(data?.jobs.shortlisted).toHaveLength(0);
      expect(data?.jobs.applied?.[0]?.id).toBe("j1");
      expect(data?.jobs.applied?.[0]?.state).toBe("applied");
    });
  });

  it("si la API falla, hace rollback del cache", async () => {
    api.setState.mockRejectedValue(new Error("boom"));
    const qc = makeQueryClient();
    qc.setQueryData(qk.board, board);
    const { result } = renderHook(() => useSetJobState(), { wrapper: wrapperFor(qc) });
    result.current.mutate({ id: "j1", state: "applied" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const data = qc.getQueryData<BoardData>(qk.board);
    expect(data?.jobs.shortlisted?.[0]?.id).toBe("j1");
  });
});
```

- [ ] **Step 3: Correrlos y verlos fallar**

Run: `npm --prefix dashboard/frontend test -- src/hooks/hooks.test.tsx`
Expected: FAIL — `Cannot find module '../test/utils'` / `'./useBoard'`.

- [ ] **Step 4: Implementar `queryClient`, `keys` y el helper de test**

`dashboard/frontend/src/lib/queryClient.ts`:

```ts
import { QueryClient } from "@tanstack/react-query";

// Cliente único de la app. staleTime corto: el dashboard es local (127.0.0.1),
// pero evita refetch en cascada al montar varias vistas que comparten queries.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});
```

`dashboard/frontend/src/hooks/keys.ts`:

```ts
// Única fuente de query keys. Nunca escribir un array-key a mano fuera de aquí.
export const qk = {
  overview: ["overview"] as const,
  board: ["board"] as const,
  job: (id: string) => ["job", id] as const,
  profiles: ["profiles"] as const,
  onboarding: ["onboarding"] as const,
  settings: ["settings"] as const,
  csvColumns: ["csv-columns"] as const,
  cvLibrary: ["cv-library"] as const,
  portfolio: ["portfolio"] as const,
  peers: ["peers"] as const,
  portfolioResearch: ["portfolio-research"] as const,
};
```

`dashboard/frontend/src/test/utils.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
}

export function renderWithQuery(ui: ReactElement) {
  const qc = makeQueryClient();
  function Providers({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return render(ui, { wrapper: Providers });
}
```

- [ ] **Step 5: Implementar `useBoard` (query + mutación optimista)**

`dashboard/frontend/src/hooks/useBoard.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../api";
import { qk } from "./keys";

export type BoardData = { columns: string[]; jobs: Record<string, Job[]>; dismissed: Job[] };

export function useBoard(enabled = true) {
  return useQuery({ queryKey: qk.board, queryFn: api.board, enabled });
}

// Mutación única de estado (move / dismiss / restore). Move optimista en cache
// con rollback en error — reemplaza el setJobs() manual de App.tsx.
export function useSetJobState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: string }) => api.setState(id, state),
    onMutate: async ({ id, state }) => {
      await qc.cancelQueries({ queryKey: qk.board });
      const prev = qc.getQueryData<BoardData>(qk.board);
      if (prev) {
        const jobs: Record<string, Job[]> = {};
        let moved: Job | undefined;
        for (const c of Object.keys(prev.jobs)) {
          jobs[c] = prev.jobs[c].filter((j) => {
            if (j.id === id) {
              moved = j;
              return false;
            }
            return true;
          });
        }
        if (moved && jobs[state]) jobs[state] = [{ ...moved, state }, ...jobs[state]];
        qc.setQueryData<BoardData>(qk.board, { ...prev, jobs });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(qk.board, ctx.prev);
    },
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: qk.board });
      qc.invalidateQueries({ queryKey: qk.overview });
      qc.invalidateQueries({ queryKey: qk.job(id) });
    },
  });
}
```

- [ ] **Step 6: Correr los tests de hooks y verlos pasar**

Run: `npm --prefix dashboard/frontend test -- src/hooks/hooks.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 7: Implementar el resto de hooks (mismo patrón, sin test unitario propio — los cubren los tests de páginas)**

`dashboard/frontend/src/hooks/useOverview.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useOverview(enabled = true) {
  return useQuery({ queryKey: qk.overview, queryFn: api.overview, enabled });
}
```

`dashboard/frontend/src/hooks/useJob.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useJob(id?: string) {
  return useQuery({
    queryKey: qk.job(id ?? ""),
    queryFn: () => api.job(id as string),
    enabled: !!id,
  });
}

function useInvalidateJob() {
  const qc = useQueryClient();
  return (id: string) => {
    qc.invalidateQueries({ queryKey: qk.job(id) });
    qc.invalidateQueries({ queryKey: qk.board });
    qc.invalidateQueries({ queryKey: qk.overview });
  };
}

export function usePrepJob() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: ({ id, language }: { id: string; language?: string }) => api.prep(id, language),
    onSettled: (_d, _e, { id }) => invalidate(id),
  });
}

export function useMarkApplied() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: (id: string) => api.markApplied(id),
    onSettled: (_d, _e, id) => invalidate(id),
  });
}

export function useRecordOutcome() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof api.recordOutcome>[1] }) =>
      api.recordOutcome(id, body),
    onSettled: (_d, _e, { id }) => invalidate(id),
  });
}
```

`dashboard/frontend/src/hooks/useProfiles.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useProfiles() {
  return useQuery({ queryKey: qk.profiles, queryFn: api.profiles });
}

// Cambiar de perfil cambia TODO el universo de datos → invalidación total.
export function useSwitchProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.switchProfile(id),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useRenameProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, label }: { id: string; label: string }) => api.renameProfile(id, label),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.profiles }),
  });
}
```

`dashboard/frontend/src/hooks/useOnboarding.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useOnboarding() {
  return useQuery({ queryKey: qk.onboarding, queryFn: api.onboarding });
}

export function useCompleteOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.completeOnboarding(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.onboarding });
      qc.invalidateQueries({ queryKey: qk.board });
      qc.invalidateQueries({ queryKey: qk.overview });
    },
  });
}
```

`dashboard/frontend/src/hooks/useSettings.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useSettings(enabled = true) {
  return useQuery({ queryKey: qk.settings, queryFn: api.settings, enabled });
}

export function useSetSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => api.setSetting(key, value),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.settings });
      qc.invalidateQueries({ queryKey: qk.csvColumns });
    },
  });
}

export function useCsvColumns(enabled = true) {
  return useQuery({ queryKey: qk.csvColumns, queryFn: api.csvColumns, enabled });
}

export function useCvLibrary(enabled = true) {
  return useQuery({ queryKey: qk.cvLibrary, queryFn: api.cvLibrary, enabled });
}
```

`dashboard/frontend/src/hooks/usePortfolio.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Peer } from "../api";
import { qk } from "./keys";

export function usePortfolioLatest() {
  return useQuery({ queryKey: qk.portfolio, queryFn: api.portfolioLatest });
}

export function usePeers() {
  return useQuery({ queryKey: qk.peers, queryFn: api.peers });
}

export function usePortfolioResearch() {
  return useQuery({ queryKey: qk.portfolioResearch, queryFn: api.portfolioResearch });
}

export function useGeneratePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (includeGithub: boolean) => api.generatePortfolio(includeGithub),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.portfolio }),
  });
}

export function useAddPeer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Peer>) => api.addPeer(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.peers }),
  });
}
```

`dashboard/frontend/src/hooks/useDiscover.ts` (porta el `buscarAhora` + contador de App.tsx tal cual, con invalidación global al terminar):

```ts
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type Overview } from "../api";

const SEARCH_SOURCES_FALLBACK = "las fuentes activas de tu perfil";

export function searchSourcesLabel(ov?: Overview | null): string {
  const names = (ov?.source_health || []).map((s) => s.source).filter(Boolean);
  return names.length > 0 ? names.join(" · ") : SEARCH_SOURCES_FALLBACK;
}

// Dispara discover→score determinista, pollea /api/discover/status (~2 min máx)
// y refresca todas las queries al terminar. Un solo dueño: AppShell.
export function useDiscover(ov?: Overview | null) {
  const qc = useQueryClient();
  const [searching, setSearching] = useState(false);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!searching) return;
    setSeconds(0);
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [searching]);

  const run = useCallback(async () => {
    if (searching) return;
    setSearching(true);
    const tid = toast.loading("Buscando vacantes nuevas…", {
      description: `Consultando fuentes y puntuando contra tu CV. ${searchSourcesLabel(ov)}`,
    });
    try {
      await api.discover();
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const { running } = await api.discoverStatus();
        if (!running) break;
      }
      await qc.invalidateQueries();
      toast.success("Búsqueda completa", {
        id: tid,
        description: "Tablero actualizado. Revisá la columna “Preseleccionados”.",
      });
    } catch {
      toast.error("No se pudo completar la búsqueda", { id: tid });
    } finally {
      setSearching(false);
    }
  }, [searching, ov, qc]);

  return { searching, seconds, run };
}
```

- [ ] **Step 8: Verificación completa**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test`
Expected: PASS. (Los hooks aún no tienen consumidores — lint no debe quejarse porque son módulos exportados.)

- [ ] **Step 9: Commit**

```bash
git add dashboard/frontend/src/lib/queryClient.ts dashboard/frontend/src/hooks/keys.ts dashboard/frontend/src/hooks/useOverview.ts dashboard/frontend/src/hooks/useBoard.ts dashboard/frontend/src/hooks/useJob.ts dashboard/frontend/src/hooks/useProfiles.ts dashboard/frontend/src/hooks/useOnboarding.ts dashboard/frontend/src/hooks/useSettings.ts dashboard/frontend/src/hooks/usePortfolio.ts dashboard/frontend/src/hooks/useDiscover.ts dashboard/frontend/src/hooks/hooks.test.tsx dashboard/frontend/src/test/utils.tsx dashboard/frontend/package.json dashboard/frontend/package-lock.json
git commit -m "feat(data): capa de datos TanStack Query — hooks por recurso con invalidación declarativa

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Backend — SPA fallback para rutas profundas

**Files:**
- Modify: `dashboard/backend/main.py:797-801` (bloque "Serve the built frontend")
- Test: `tests/test_backend_api.py` (añadir al final)

**Interfaces:**
- Consumes: `_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"` (ya definido en main.py:799), `FileResponse` (ya importado línea 19), fixture `atlas_app` de `tests/conftest.py`.
- Produces: `GET /{full_path:path}` — sirve el archivo real si existe bajo `dist/`, `index.html` para cualquier otra ruta (deep links `/pipeline`, `/jobs/:id`, …), y 404 para `/api/*` desconocidos y para todo si `dist/` no está compilado. Las Tasks 5-8 dependen de esto para que `scripts/run.sh` sirva el router.

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_backend_api.py`:

```python
# ── SPA fallback (Atlas v2 F1): el router de frontend necesita deep links ────


def test_spa_fallback_serves_index_for_client_routes(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>atlas-spa</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(backend, "_DIST", dist)

    with TestClient(atlas_app) as client:
        for path in ("/", "/pipeline", "/jobs/abc123", "/settings", "/onboarding"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert "atlas-spa" in resp.text, path
        # los archivos reales del build se sirven tal cual
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text


def test_spa_fallback_unknown_api_route_is_404_not_index(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>atlas-spa</html>")
    monkeypatch.setattr(backend, "_DIST", dist)

    with TestClient(atlas_app) as client:
        assert client.get("/api/definitely-not-a-route").status_code == 404


def test_spa_fallback_without_built_dist_is_404(atlas_app, tmp_path, monkeypatch):
    import dashboard.backend.main as backend

    monkeypatch.setattr(backend, "_DIST", tmp_path / "no-dist")
    with TestClient(atlas_app) as client:
        assert client.get("/pipeline").status_code == 404
```

- [ ] **Step 2: Correrlos y verlos fallar**

Run: `rtk uv run --group dev pytest tests/test_backend_api.py -k spa_fallback`
Expected: FAIL — con el mount actual (`StaticFiles`), `/pipeline` devuelve 404 (o el mount ni existe si `dist/` no está compilado en el entorno de test).

- [ ] **Step 3: Reemplazar el mount por el catch-all**

En `dashboard/backend/main.py`, reemplazar las líneas 797-801:

```python
# ── Serve the built frontend (if present) ────────────────────────────────────
# Mounted LAST so it never shadows the /api/* routes.
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
```

por:

```python
# ── Serve the built frontend (SPA) ───────────────────────────────────────────
# Catch-all definido AL FINAL para no sombrear /api/*. Sirve archivos reales del
# build cuando existen y hace fallback a index.html para las rutas del router
# (deep links /pipeline, /jobs/:id, …). Lee _DIST en call-time (testeable).
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    if full_path:
        candidate = (_DIST / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(_DIST.resolve()):
            return FileResponse(str(candidate))
    index = _DIST / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend no compilado — corre scripts/run.sh (o npm run build).",
        )
    return FileResponse(str(index))
```

Además: eliminar `from fastapi.staticfiles import StaticFiles` (línea 20) — queda sin uso y ruff lo marcaría. Verificar que `HTTPException` ya está importado (lo está: se usa en los endpoints 404 existentes).

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `rtk uv run --group dev pytest tests/test_backend_api.py -k spa_fallback`
Expected: PASS (3 tests).

- [ ] **Step 5: Suite backend completa + lint Python**

Run: `uv run ruff check . && uv run ruff format --check . && rtk uv run --group dev pytest`
Expected: PASS (117+ tests, cero regresiones — el resto de endpoints no cambió).

- [ ] **Step 6: Commit**

```bash
git add dashboard/backend/main.py tests/test_backend_api.py
git commit -m "feat(backend): SPA fallback — index.html para deep links del router, 404 para /api desconocidas

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Router v7 + AppShell (sidebar/header) + PipelinePage + OnboardingPage

**Files:**
- Create: `dashboard/frontend/src/hooks/useTheme.ts`
- Create: `dashboard/frontend/src/routes.tsx`
- Create: `dashboard/frontend/src/components/AppShell.tsx`
- Create: `dashboard/frontend/src/pages/PipelinePage.tsx`
- Create: `dashboard/frontend/src/pages/AnalyticsPage.tsx`
- Create: `dashboard/frontend/src/pages/PortfolioPage.tsx`
- Create: `dashboard/frontend/src/pages/OnboardingPage.tsx`
- Modify: `dashboard/frontend/src/App.tsx` (reemplazo completo — queda como providers)
- Modify: `dashboard/frontend/src/components/CommandPalette.tsx` (reemplazo completo)
- Modify: `dashboard/frontend/src/test/utils.tsx` (añadir `renderRoutes`)
- Test: `dashboard/frontend/src/components/AppShell.test.tsx`
- Test: `dashboard/frontend/src/pages/PipelinePage.test.tsx`

**Interfaces:**
- Consumes: hooks de Task 3 (firmas exactas de su bloque Produces), tokens sidebar de Task 1 (`bg-sidebar`, `text-sidebar-foreground`, `border-sidebar-border`, `bg-sidebar-active`, `text-sidebar-active-foreground`), componentes existentes sin cambios: `Board`, `NeedsAction`, `FilterBar` (+ tipo `Filters`), `AnalyticsStrip`, `PortfolioViewer`, `OnboardingGate`, `HelpGuide`, `CvAuditDialog`, `SettingsModal` (temporal hasta Task 6), `DetailDrawer` (temporal hasta Task 8).
- Produces:
  - Rutas canónicas de Atlas v2 (las Fases 2-4 añaden las suyas aquí): `/` → redirect `/pipeline` · `/pipeline` · `/jobs/:id` · `/analytics` · `/portfolio` · `/settings` (Task 6; en esta task el gear abre el modal) · `/onboarding` · `*` → redirect `/pipeline`.
  - `export const routes: RouteObject[]` en `src/routes.tsx` (los tests montan `createMemoryRouter(routes, { initialEntries })`).
  - `export function AppShell(): JSX.Element` — layout con `<Outlet />`; dueño único de: guard de onboarding, tema, CommandPalette, Toaster, HelpGuide, CvAuditDialog, diálogo de brief, botón Buscar (`useDiscover`).
  - `export function useTheme(): { theme: "dark" | "light"; toggle: () => void }`.
  - `CommandPalette` nueva firma: `{ open: boolean; setOpen: (o: boolean) => void; jobs: Job[]; onNavigate: (to: string) => void; onSearch: () => void; onBrief: () => void; onRefresh: () => void }`.
  - `renderRoutes(initialPath: string)` en `src/test/utils.tsx` — monta `routes` con QueryClient fresco + memory router y devuelve el resultado de `render`.

- [ ] **Step 1: Instalar react-router**

```bash
npm --prefix dashboard/frontend install react-router@^7
```

- [ ] **Step 2: Escribir los tests que fallan (shell + redirect + guard)**

Crear `dashboard/frontend/src/components/AppShell.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

const onboardingDone = {
  complete: true,
  profile: "owner",
  cv_present: true,
  audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
};
const emptyOverview = {
  overview: {
    total_jobs: 0,
    counts: {},
    funnel: [],
    response_rate: null,
    interview_rate: null,
    applied: 0,
    ready: 0,
    source_health: [],
  },
  needs_action: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue(onboardingDone);
  api.overview.mockResolvedValue(emptyOverview);
  api.board.mockResolvedValue({ columns: ["shortlisted"], jobs: { shortlisted: [] }, dismissed: [] });
});

describe("AppShell + router", () => {
  it("/ redirige a /pipeline y muestra la navegación", async () => {
    renderRoutes("/");
    expect(await screen.findByRole("link", { name: /Pipeline/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Analítica/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Portafolio/ })).toBeInTheDocument();
    // contenido del pipeline (empty state del NeedsAction)
    expect(await screen.findByText(/Todo al día/)).toBeInTheDocument();
  });

  it("con onboarding incompleto redirige a /onboarding", async () => {
    api.onboarding.mockResolvedValue({ ...onboardingDone, complete: false });
    renderRoutes("/pipeline");
    expect(await screen.findByText(/Primer paso: adapta tu CV/)).toBeInTheDocument();
    await waitFor(() => expect(api.board).not.toHaveBeenCalled());
  });

  it("una ruta desconocida cae en /pipeline", async () => {
    renderRoutes("/no-existe");
    expect(await screen.findByText(/Todo al día/)).toBeInTheDocument();
  });
});
```

Crear `dashboard/frontend/src/pages/PipelinePage.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    setState: vi.fn(),
    job: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

const job = {
  id: "j1",
  title: "Data Scientist",
  company: "Acme",
  state: "shortlisted",
  fit_score: 80,
  is_remote: 1,
};

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: true,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.overview.mockResolvedValue({
    overview: {
      total_jobs: 1,
      counts: { shortlisted: 1 },
      funnel: [],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
    },
    needs_action: [],
  });
  api.board.mockResolvedValue({
    columns: ["shortlisted"],
    jobs: { shortlisted: [job] },
    dismissed: [],
  });
  api.setState.mockResolvedValue({ ok: true });
});

describe("PipelinePage", () => {
  it("renderiza el tablero con la vacante", async () => {
    renderRoutes("/pipeline");
    expect(await screen.findByText("Data Scientist")).toBeInTheDocument();
    expect(screen.getByText("Preseleccionados")).toBeInTheDocument();
  });

  it("descartar una card llama setState('dismissed')", async () => {
    renderRoutes("/pipeline");
    await screen.findByText("Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(api.setState).toHaveBeenCalledWith("j1", "dismissed");
  });

  it("las descartadas se listan y se pueden restaurar", async () => {
    api.board.mockResolvedValue({
      columns: ["shortlisted"],
      jobs: { shortlisted: [] },
      dismissed: [job],
    });
    renderRoutes("/pipeline");
    await userEvent.click(await screen.findByText(/Descartadas \(1\)/));
    await userEvent.click(screen.getByRole("button", { name: /Restaurar/ }));
    expect(api.setState).toHaveBeenCalledWith("j1", "shortlisted");
  });
});
```

- [ ] **Step 3: Correrlos y verlos fallar**

Run: `npm --prefix dashboard/frontend test -- src/components/AppShell.test.tsx src/pages/PipelinePage.test.tsx`
Expected: FAIL — `renderRoutes` no existe / `src/routes.tsx` no existe.

- [ ] **Step 4: `useTheme` + `renderRoutes`**

`dashboard/frontend/src/hooks/useTheme.ts`:

```ts
import { useCallback, useEffect, useState } from "react";

// data-theme en <html> + persistencia. main.tsx ya lo aplica pre-paint.
export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    localStorage.getItem("atlas-theme") === "light" ? "light" : "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("atlas-theme", theme);
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}
```

Añadir a `dashboard/frontend/src/test/utils.tsx` (debajo de `renderWithQuery`):

```tsx
import { createMemoryRouter, RouterProvider } from "react-router";
import { TooltipProvider } from "../components/ui/tooltip";
import { routes } from "../routes";

export function renderRoutes(initialPath: string) {
  const qc = makeQueryClient();
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] });
  return render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}
```

(Consolidar los imports arriba del archivo: `render` ya está importado.)

- [ ] **Step 5: `routes.tsx` + `App.tsx` (providers)**

`dashboard/frontend/src/routes.tsx`:

```tsx
import { Navigate, type RouteObject } from "react-router";
import { AppShell } from "./components/AppShell";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PipelinePage } from "./pages/PipelinePage";
import { PortfolioPage } from "./pages/PortfolioPage";

// /jobs/:id nace apuntando al DetailDrawer sobre el pipeline (paridad) y la
// Task 8 lo reemplaza por la página completa JobDetailPage.
import { JobDetailRoute } from "./pages/PipelinePage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/pipeline" replace /> },
      { path: "pipeline", element: <PipelinePage /> },
      { path: "jobs/:id", element: <JobDetailRoute /> },
      { path: "analytics", element: <AnalyticsPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "onboarding", element: <OnboardingPage /> },
      { path: "*", element: <Navigate to="/pipeline" replace /> },
    ],
  },
];
```

`dashboard/frontend/src/App.tsx` (reemplazo completo del archivo):

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { TooltipProvider } from "./components/ui/tooltip";
import { queryClient } from "./lib/queryClient";
import { routes } from "./routes";

// App = solo providers. Todo el layout vive en AppShell; los datos, en src/hooks/.
export default function App() {
  const router = useMemo(() => createBrowserRouter(routes), []);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 6: `AppShell.tsx`**

`dashboard/frontend/src/components/AppShell.tsx` (completo):

```tsx
import {
  ChartNoAxesColumn,
  Command as CmdIcon,
  FileText,
  Globe,
  HelpCircle,
  Kanban,
  Loader2,
  Moon,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../api";
import { useBoard } from "../hooks/useBoard";
import { useDiscover, searchSourcesLabel } from "../hooks/useDiscover";
import { useOnboarding } from "../hooks/useOnboarding";
import { useOverview } from "../hooks/useOverview";
import { useProfiles, useSwitchProfile } from "../hooks/useProfiles";
import { useTheme } from "../hooks/useTheme";
import { cn } from "../lib";
import { CommandPalette } from "./CommandPalette";
import { CvAuditDialog } from "./CvAuditDialog";
import { HelpGuide } from "./HelpGuide";
import { SettingsModal } from "./SettingsModal"; // Task 6 lo reemplaza por /settings
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Kbd } from "./ui/kbd";
import { ScrollArea } from "./ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Toaster } from "./ui/sonner";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const NAV = [
  { to: "/pipeline", label: "Pipeline", icon: Kanban },
  { to: "/analytics", label: "Analítica", icon: ChartNoAxesColumn },
  { to: "/portfolio", label: "Portafolio", icon: Globe },
];

export function AppShell() {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();

  const onboardingQ = useOnboarding();
  const complete = onboardingQ.data?.complete === true;
  const profilesQ = useProfiles();
  const overviewQ = useOverview(complete);
  const boardQ = useBoard(complete);
  const { searching, seconds, run } = useDiscover(overviewQ.data?.overview);

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [cvOpen, setCvOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState("");

  const switchProfile = useSwitchProfile();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Guía abierta la primera vez (one-time hint) — conservado de v1.
  useEffect(() => {
    if (!localStorage.getItem("atlas-guide-seen")) {
      setHelpOpen(true);
      localStorage.setItem("atlas-guide-seen", "1");
    }
  }, []);

  if (onboardingQ.isPending || profilesQ.isPending) {
    return (
      <div className="grid min-h-full place-items-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Guard de onboarding: sin CV listo no hay tablero (paridad con el gate v1).
  if (!complete && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  if (complete && location.pathname === "/onboarding") {
    return <Navigate to="/pipeline" replace />;
  }

  const ov = overviewQ.data?.overview;
  const allJobs = Object.values(boardQ.data?.jobs ?? {}).flat();

  async function openBrief() {
    const b = await api.brief();
    setBrief(b.markdown);
    setBriefOpen(true);
  }

  async function onSwitchProfile(id: string) {
    if (id === profilesQ.data?.active) return;
    await switchProfile.mutateAsync(id);
    navigate("/pipeline");
  }

  return (
    <div className="flex min-h-full">
      {/* ── Sidebar ── */}
      <aside className="sticky top-0 flex h-screen w-52 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 text-sidebar-foreground max-lg:w-14">
        <div className="mb-6 flex items-center gap-2.5 px-1.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary font-bold text-primary-foreground">
            A
          </div>
          <div className="min-w-0 max-lg:hidden">
            <div className="leading-none font-semibold tracking-tight">Atlas</div>
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="mt-0.5 block truncate text-[0.68rem] text-muted-foreground transition-colors hover:text-foreground"
            >
              {ov?.last_run
                ? `corrida ${new Date(ov.last_run).toLocaleDateString("es")}`
                : "sin corridas"}
            </button>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-active text-sidebar-active-foreground"
                    : "text-muted-foreground hover:bg-sidebar-active/50 hover:text-foreground",
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              <span className="max-lg:hidden">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-1">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-active/50 hover:text-foreground"
          >
            <SettingsIcon className="size-4 shrink-0" />
            <span className="max-lg:hidden">Ajustes</span>
          </button>
          <button
            type="button"
            onClick={toggle}
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-active/50 hover:text-foreground"
          >
            {theme === "dark" ? (
              <Sun className="size-4 shrink-0" />
            ) : (
              <Moon className="size-4 shrink-0" />
            )}
            <span className="max-lg:hidden">Tema</span>
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-2">
            {(profilesQ.data?.profiles.length ?? 0) > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Select value={profilesQ.data?.active ?? ""} onValueChange={onSwitchProfile}>
                    <SelectTrigger size="sm" className="w-auto" aria-label="Perfil activo">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {profilesQ.data?.profiles.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.label}
                          {p.is_owner ? " ★" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TooltipTrigger>
                <TooltipContent>
                  Perfil activo. Cada perfil es una cuenta local con su propio CV, base de datos y
                  configuración.
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="sm" onClick={run} disabled={searching}>
                  {searching ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Search className="size-3.5" />
                  )}
                  {searching ? `Buscando… ${seconds}s` : "Buscar"}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <b>Buscar vacantes</b> — trae ofertas nuevas de todas las fuentes y las puntúa
                contra tu CV (discover + score). Es Python determinista (sin IA), tarda ~1–2 min.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPaletteOpen(true)}
                  className="gap-1.5"
                >
                  <CmdIcon className="size-3.5" /> <Kbd>K</Kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Paleta de comandos (⌘/Ctrl + K) — navega o salta a una vacante al instante.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setHelpOpen(true)}>
                  <HelpCircle className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Cómo funciona Atlas — guía de funcionalidades.</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setCvOpen(true)}>
                  <FileText className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Auditoría de tu CV — score y recomendaciones.</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => qc.invalidateQueries()}>
                  <RefreshCw className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Actualizar (relee la base de datos local)</TooltipContent>
            </Tooltip>
          </div>
        </header>

        {searching && (
          <Card className="fade-up mx-5 mt-4 flex items-center gap-3 border-primary/40 p-3.5">
            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                Buscando vacantes nuevas… <span className="tabular-nums">{seconds}s</span>
              </div>
              <div className="truncate text-[0.78rem] text-muted-foreground">
                Consultando fuentes y puntuando contra tu CV · {searchSourcesLabel(ov)}
              </div>
              <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-secondary">
                <div className="h-full w-1/3 animate-[indet_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
              </div>
            </div>
          </Card>
        )}

        <main className="mx-auto w-full max-w-[1500px] flex-1 px-5 py-4">
          <Outlet />
        </main>
      </div>

      {/* ── Global overlays ── */}
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <HelpGuide open={helpOpen} onOpenChange={setHelpOpen} />
      <CvAuditDialog open={cvOpen} onOpenChange={setCvOpen} />
      <CommandPalette
        open={paletteOpen}
        setOpen={setPaletteOpen}
        jobs={allJobs}
        onNavigate={(to) => navigate(to)}
        onSearch={run}
        onBrief={openBrief}
        onRefresh={() => qc.invalidateQueries()}
      />

      <Dialog open={briefOpen} onOpenChange={setBriefOpen}>
        <DialogContent className="max-w-[640px]">
          <DialogHeader>
            <DialogTitle>Resumen del día</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[70vh]">
            <pre className="font-sans text-[0.82rem] whitespace-pre-wrap text-foreground">
              {brief}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <Toaster theme={theme} />
    </div>
  );
}
```

- [ ] **Step 7: `PipelinePage.tsx` (+ `JobDetailRoute` temporal)**

`dashboard/frontend/src/pages/PipelinePage.tsx` (completo):

```tsx
import { RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import type { Job } from "../api";
import { Board } from "../components/Board";
import { DetailDrawer } from "../components/DetailDrawer"; // temporal — Task 8 lo reemplaza
import { FilterBar, type Filters } from "../components/FilterBar";
import { NeedsAction } from "../components/NeedsAction";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { DowntimeIcon } from "../components/ui/icons";
import { Skeleton } from "../components/ui/skeleton";
import { useBoard, useSetJobState } from "../hooks/useBoard";
import { useOverview } from "../hooks/useOverview";

export function PipelinePage() {
  const navigate = useNavigate();
  const overviewQ = useOverview();
  const boardQ = useBoard();
  const setJobState = useSetJobState();
  const [showDismissed, setShowDismissed] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    onlySalary: false,
    language: "",
    maxAgeDays: 0,
  });

  const jobs = useMemo(() => boardQ.data?.jobs ?? {}, [boardQ.data]);
  const columns = boardQ.data?.columns ?? [];
  const dismissed = boardQ.data?.dismissed ?? [];
  const actions = overviewQ.data?.needs_action ?? [];
  const ov = overviewQ.data?.overview;

  const allJobs = Object.values(jobs).flat();
  const languages = Array.from(
    new Set(allJobs.map((j) => j.language).filter((l): l is string => !!l)),
  ).sort();
  const filteredJobs = useMemo(() => {
    const out: Record<string, Job[]> = {};
    for (const c of Object.keys(jobs)) {
      out[c] = jobs[c].filter((j) => {
        const age = j.posted_days ?? j.age_days;
        return (
          (!filters.onlySalary || j.salary_visible) &&
          (!filters.language || j.language === filters.language) &&
          (!filters.maxAgeDays || age == null || age <= filters.maxAgeDays)
        );
      });
    }
    return out;
  }, [jobs, filters]);

  const open = (id: string) => navigate(`/jobs/${id}`);
  const move = (jobId: string, to: string) => setJobState.mutate({ id: jobId, state: to });

  function dismiss(jobId: string, from: string) {
    setJobState.mutate(
      { id: jobId, state: "dismissed" },
      {
        onSuccess: () =>
          toast.success("Vacante descartada", {
            description: "No volverá a aparecer en tu tablero.",
            action: {
              label: "Deshacer",
              onClick: () => setJobState.mutate({ id: jobId, state: from }),
            },
          }),
      },
    );
  }

  function restore(jobId: string) {
    setJobState.mutate(
      { id: jobId, state: "shortlisted" },
      { onSuccess: () => toast.success("Vacante restaurada a Preseleccionados") },
    );
  }

  if (boardQ.isPending || overviewQ.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <div className="flex gap-3">
          <Skeleton className="h-64 flex-1" />
          <Skeleton className="h-64 flex-1" />
          <Skeleton className="h-64 flex-1" />
        </div>
      </div>
    );
  }

  return (
    <>
      {ov?.downtime_hours ? (
        <Card className="mb-4 flex items-center gap-2 border-warning/50 p-3 text-sm">
          <DowntimeIcon className="size-4 shrink-0 text-warning" />
          Estuve sin correr ~{Math.round(ov.downtime_hours)}h. Revisa que el Mac esté despierto y
          Claude Desktop abierto.
        </Card>
      ) : null}

      <div className="mb-6">
        <NeedsAction actions={actions} onOpen={open} />
      </div>

      <FilterBar filters={filters} setFilters={setFilters} languages={languages} />
      <Board
        columns={columns}
        jobs={filteredJobs}
        onOpen={open}
        onMove={move}
        onDismiss={dismiss}
      />

      {dismissed.length > 0 && (
        <div className="mt-5">
          <button
            type="button"
            onClick={() => setShowDismissed((v) => !v)}
            className="inline-flex items-center gap-1.5 text-caption text-muted-foreground uppercase transition-colors hover:text-foreground"
          >
            <Trash2 className="size-3.5" />
            Descartadas ({dismissed.length}) {showDismissed ? "▾" : "▸"}
          </button>
          {showDismissed && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {dismissed.map((j) => (
                <Card key={j.id} className="flex items-center justify-between gap-2 p-3 text-sm">
                  <button type="button" onClick={() => open(j.id)} className="min-w-0 text-left">
                    <div className="truncate font-medium">{j.title}</div>
                    <div className="truncate text-xs text-muted-foreground">{j.company}</div>
                  </button>
                  <Button variant="secondary" size="sm" onClick={() => restore(j.id)}>
                    <RotateCcw className="size-3.5" /> Restaurar
                  </Button>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}

// Ruta temporal /jobs/:id: pipeline de fondo + DetailDrawer encima (paridad
// exacta con v1). La Task 8 borra este componente y monta JobDetailPage.
export function JobDetailRoute() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  return (
    <>
      <PipelinePage />
      <DetailDrawer
        jobId={id ?? null}
        onClose={() => navigate("/pipeline")}
        onChanged={() => qc.invalidateQueries()}
      />
    </>
  );
}
```

- [ ] **Step 8: Páginas delgadas — Analytics, Portfolio, Onboarding**

`dashboard/frontend/src/pages/AnalyticsPage.tsx`:

```tsx
import { AnalyticsStrip } from "../components/AnalyticsStrip";
import { Skeleton } from "../components/ui/skeleton";
import { useOverview } from "../hooks/useOverview";

export function AnalyticsPage() {
  const overviewQ = useOverview();
  if (overviewQ.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!overviewQ.data) return null;
  return (
    <>
      <h1 className="mb-4 text-h1">Analítica</h1>
      <AnalyticsStrip ov={overviewQ.data.overview} />
    </>
  );
}
```

`dashboard/frontend/src/pages/PortfolioPage.tsx`:

```tsx
import { PortfolioViewer } from "../components/PortfolioViewer";
import { useProfiles } from "../hooks/useProfiles";

export function PortfolioPage() {
  const profilesQ = useProfiles();
  // key por perfil activo: al cambiar de perfil se refetchea portfolio/peers/research
  return <PortfolioViewer key={profilesQ.data?.active ?? ""} />;
}
```

`dashboard/frontend/src/pages/OnboardingPage.tsx`:

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { OnboardingGate } from "../components/OnboardingGate";
import { Skeleton } from "../components/ui/skeleton";
import { qk } from "../hooks/keys";
import { useOnboarding } from "../hooks/useOnboarding";

export function OnboardingPage() {
  const onboardingQ = useOnboarding();
  const qc = useQueryClient();
  if (onboardingQ.isPending) return <Skeleton className="mx-auto mt-8 h-96 max-w-[760px]" />;
  if (!onboardingQ.data) return null;
  return (
    <OnboardingGate
      status={onboardingQ.data}
      onComplete={() => qc.invalidateQueries()}
      onRefresh={() => qc.invalidateQueries({ queryKey: qk.onboarding })}
    />
  );
}
```

(Al completar, la invalidación refresca `onboarding` → el guard del shell redirige solo a `/pipeline`.)

- [ ] **Step 9: `CommandPalette.tsx` integrada a navegación (reemplazo completo)**

```tsx
import { Command as CmdkCommand } from "cmdk";
import {
  ChartNoAxesColumn,
  FileText,
  Globe,
  Kanban,
  RefreshCw,
  Settings as SettingsIcon,
  Sparkles,
} from "lucide-react";
import type { Job } from "../api";
import { STATE_ES } from "../lib";
import {
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "./ui/command";

const GOTO = [
  { to: "/pipeline", label: "Ir a Pipeline", icon: Kanban },
  { to: "/analytics", label: "Ir a Analítica", icon: ChartNoAxesColumn },
  { to: "/portfolio", label: "Ir a Portafolio", icon: Globe },
  { to: "/settings", label: "Ir a Ajustes", icon: SettingsIcon },
];

export function CommandPalette({
  open,
  setOpen,
  jobs,
  onNavigate,
  onSearch,
  onBrief,
  onRefresh,
}: {
  open: boolean;
  setOpen: (o: boolean) => void;
  jobs: Job[];
  onNavigate: (to: string) => void;
  onSearch: () => void;
  onBrief: () => void;
  onRefresh: () => void;
}) {
  const go = (fn: () => void) => () => {
    fn();
    setOpen(false);
  };
  return (
    <CmdkCommand.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Atlas command palette"
      className="fixed inset-0 z-[80] flex items-start justify-center pt-[12vh]"
      overlayClassName="fixed inset-0 z-[79] bg-black/55 backdrop-blur-[3px]"
      contentClassName="relative z-[81]"
    >
      <div className="w-[600px] max-w-[92vw] overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-[var(--shadow-lg)]">
        <CommandInput autoFocus placeholder="Busca una vista, vacante o acción…" />
        <CommandList>
          <CommandEmpty>Sin resultados.</CommandEmpty>
          <CommandGroup heading="Ir a">
            {GOTO.map(({ to, label, icon: Icon }) => (
              <CommandItem key={to} value={label} onSelect={go(() => onNavigate(to))}>
                <Icon /> {label}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Acciones">
            <CommandItem value="buscar vacantes nuevas" onSelect={go(onSearch)}>
              <Sparkles /> Buscar vacantes nuevas
            </CommandItem>
            <CommandItem value="actualizar tablero" onSelect={go(onRefresh)}>
              <RefreshCw /> Actualizar tablero
            </CommandItem>
            <CommandItem value="abrir resumen del dia" onSelect={go(onBrief)}>
              <FileText /> Abrir resumen del día
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Vacantes">
            {jobs.map((j) => (
              <CommandItem
                key={j.id}
                value={`${j.title} ${j.company} ${j.id}`}
                onSelect={go(() => onNavigate(`/jobs/${j.id}`))}
              >
                <span className="flex-1 truncate">
                  {j.title} <span className="text-muted-foreground">— {j.company}</span>
                </span>
                <CommandShortcut>
                  {j.fit_score ?? "—"} · {STATE_ES[j.state] || j.state}
                </CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </div>
    </CmdkCommand.Dialog>
  );
}
```

Nota: `/settings` cae en `*` → `/pipeline` hasta la Task 6; el gear del sidebar abre el modal mientras tanto. La Task 6 elimina esa asimetría.

- [ ] **Step 10: Correr los tests nuevos y verlos pasar**

Run: `npm --prefix dashboard/frontend test -- src/components/AppShell.test.tsx src/pages/PipelinePage.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 11: Suite completa + typecheck + build**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run build`
Expected: todo PASS. Los tests viejos de Board/NeedsAction/DetailDrawer/api siguen verdes (componentes intactos).

- [ ] **Step 12: QA con preview tools**

Backend corriendo + dev server: navegar `/` (→ `/pipeline`), `/analytics`, `/portfolio`, `/onboarding` (con perfil incompleto), ⌘K → "Ir a Analítica", click en una card → URL `/jobs/<id>` con drawer. Verificar en dark y light.

- [ ] **Step 13: Commit**

```bash
git add dashboard/frontend/src/App.tsx dashboard/frontend/src/routes.tsx dashboard/frontend/src/components/AppShell.tsx dashboard/frontend/src/components/AppShell.test.tsx dashboard/frontend/src/components/CommandPalette.tsx dashboard/frontend/src/hooks/useTheme.ts dashboard/frontend/src/pages/PipelinePage.tsx dashboard/frontend/src/pages/PipelinePage.test.tsx dashboard/frontend/src/pages/AnalyticsPage.tsx dashboard/frontend/src/pages/PortfolioPage.tsx dashboard/frontend/src/pages/OnboardingPage.tsx dashboard/frontend/src/test/utils.tsx dashboard/frontend/package.json dashboard/frontend/package-lock.json
git commit -m "feat(shell): react-router v7 + app shell con sidebar — pipeline/analytics/portfolio/onboarding como rutas

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: SettingsPage — `/settings` reemplaza al SettingsModal

**Files:**
- Create: `dashboard/frontend/src/pages/SettingsPage.tsx`
- Test: `dashboard/frontend/src/pages/SettingsPage.test.tsx`
- Modify: `dashboard/frontend/src/routes.tsx` (añadir la ruta)
- Modify: `dashboard/frontend/src/components/AppShell.tsx` (gear → `NavLink` a `/settings`; quitar `SettingsModal` y su estado)
- Delete: `dashboard/frontend/src/components/SettingsModal.tsx`

**Interfaces:**
- Consumes: `useSettings()`, `useSetSetting()`, `useCsvColumns()`, `useCvLibrary()`, `useProfiles()`, `useRenameProfile()` (Task 3); `api.exportUrl(columns?: string[], state?: string): string` de `src/api.ts`; helper `copy(text: string): Promise<void>` de `src/lib`.
- Produces: ruta `/settings` funcional con las 4 secciones del modal v1 (nombre de perfil, carpeta de descarga, carpeta de CVs, diseño CSV + descarga). El CommandPalette ("Ir a Ajustes") deja de caer en el redirect `*`.

- [ ] **Step 1: Escribir el test que falla**

Crear `dashboard/frontend/src/pages/SettingsPage.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    settings: vi.fn(),
    setSetting: vi.fn(),
    csvColumns: vi.fn(),
    cvLibrary: vi.fn(),
    renameProfile: vi.fn(),
    exportUrl: (cols?: string[]) => `/api/export?columns=${(cols ?? []).join(",")}`,
  },
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: true,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.overview.mockResolvedValue({
    overview: {
      total_jobs: 0,
      counts: {},
      funnel: [],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
    },
    needs_action: [],
  });
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
  api.settings.mockResolvedValue({ download_dir: "/tmp/atlas" });
  api.csvColumns.mockResolvedValue({
    available: [
      { id: "title", label: "Título" },
      { id: "company", label: "Empresa" },
    ],
    selected: ["title"],
  });
  api.cvLibrary.mockResolvedValue({ dir: "/tmp/cvs", count: 2, files: [] });
  api.setSetting.mockResolvedValue({ ok: true, key: "download_dir", value: "/tmp/atlas2" });
});

describe("SettingsPage", () => {
  it("renderiza las cuatro secciones con datos de la API", async () => {
    renderRoutes("/settings");
    expect(await screen.findByText("Nombre de tu perfil")).toBeInTheDocument();
    expect(screen.getByText(/Carpeta de descarga/)).toBeInTheDocument();
    expect(screen.getByText(/Carpeta de tus CVs/)).toBeInTheDocument();
    expect(screen.getByText("Diseño del CSV")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("/tmp/atlas")).toBeInTheDocument();
    expect(await screen.findByText("Título")).toBeInTheDocument();
  });

  it("guardar carpeta llama a setSetting(download_dir)", async () => {
    renderRoutes("/settings");
    const input = await screen.findByDisplayValue("/tmp/atlas");
    await userEvent.clear(input);
    await userEvent.type(input, "/tmp/atlas2");
    await userEvent.click(screen.getByRole("button", { name: "Guardar carpeta" }));
    expect(api.setSetting).toHaveBeenCalledWith("download_dir", "/tmp/atlas2");
  });

  it("guardar diseño persiste las columnas seleccionadas", async () => {
    renderRoutes("/settings");
    await screen.findByText("Título");
    await userEvent.click(screen.getByRole("button", { name: "Guardar diseño" }));
    expect(api.setSetting).toHaveBeenCalledWith("csv_columns", JSON.stringify(["title"]));
  });
});
```

- [ ] **Step 2: Correrlo y verlo fallar**

Run: `npm --prefix dashboard/frontend test -- src/pages/SettingsPage.test.tsx`
Expected: FAIL — `/settings` cae en el redirect `*` → renderiza pipeline, no "Nombre de tu perfil".

- [ ] **Step 3: Implementar `SettingsPage.tsx`**

Contenido portado 1:1 del SettingsModal (mismas strings y llamadas), como página con hooks:

```tsx
import { Copy, Download, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import { Button, buttonVariants } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Separator } from "../components/ui/separator";
import { Skeleton } from "../components/ui/skeleton";
import { useCsvColumns, useCvLibrary, useSetSetting, useSettings } from "../hooks/useSettings";
import { useProfiles, useRenameProfile } from "../hooks/useProfiles";
import { copy } from "../lib";

export function SettingsPage() {
  const settingsQ = useSettings();
  const columnsQ = useCsvColumns();
  const cvLibQ = useCvLibrary();
  const profilesQ = useProfiles();
  const setSetting = useSetSetting();
  const renameProfile = useRenameProfile();

  const [downloadDir, setDownloadDir] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [profileLabel, setProfileLabel] = useState("");

  // Semilla de formularios desde las queries (una vez cargadas).
  useEffect(() => {
    if (settingsQ.data) setDownloadDir(settingsQ.data.download_dir || "");
  }, [settingsQ.data]);
  useEffect(() => {
    if (columnsQ.data) setSelected(columnsQ.data.selected);
  }, [columnsQ.data]);
  useEffect(() => {
    if (profilesQ.data) {
      setProfileLabel(
        profilesQ.data.profiles.find((x) => x.id === profilesQ.data.active)?.label || "",
      );
    }
  }, [profilesQ.data]);

  if (settingsQ.isPending || columnsQ.isPending || profilesQ.isPending) {
    return (
      <div className="mx-auto max-w-[640px] space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const activeId = profilesQ.data?.active ?? "";

  async function saveProfileName() {
    if (!activeId || !profileLabel.trim()) return;
    try {
      const r = await renameProfile.mutateAsync({ id: activeId, label: profileLabel.trim() });
      setProfileLabel(r.label);
      toast.success("Nombre del perfil guardado");
    } catch {
      toast.error("No se pudo guardar el nombre");
    }
  }

  function toggleColumn(id: string) {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  }

  async function saveDir() {
    try {
      const r = await setSetting.mutateAsync({ key: "download_dir", value: downloadDir });
      setDownloadDir(r.value);
      toast.success("Carpeta guardada");
    } catch {
      toast.error("Ruta inválida");
    }
  }

  async function saveColumns() {
    await setSetting.mutateAsync({ key: "csv_columns", value: JSON.stringify(selected) });
    toast.success("Diseño guardado");
  }

  const cvLib = cvLibQ.data;

  return (
    <div className="mx-auto max-w-[640px]">
      <h1 className="mb-1 text-h1">Ajustes</h1>
      <p className="mb-5 text-sm text-muted-foreground">
        Perfil, carpeta de descarga y diseño del CSV exportado.
      </p>

      <section className="mt-1">
        <div className="mb-1 text-sm font-semibold">Nombre de tu perfil</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Cómo se llama tu perfil en el selector de arriba.
        </div>
        <div className="flex gap-2">
          <Input
            className="flex-1"
            value={profileLabel}
            onChange={(e) => setProfileLabel(e.target.value)}
            placeholder="Tu nombre"
          />
          <Button variant="secondary" onClick={saveProfileName}>
            Guardar nombre
          </Button>
        </div>
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 text-sm font-semibold">Carpeta de descarga (CLI / brain)</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Dónde guarda <code className="font-mono">atlas export</code>. Desde el navegador, el CSV
          se descarga donde elijas en el diálogo del navegador.
        </div>
        <div className="flex gap-2">
          <Input
            className="flex-1 font-mono text-xs"
            value={downloadDir}
            onChange={(e) => setDownloadDir(e.target.value)}
            placeholder="~/Downloads/atlas"
          />
          <Button variant="secondary" onClick={saveDir}>
            Guardar carpeta
          </Button>
        </div>
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
          <FolderOpen className="size-3.5" /> Carpeta de tus CVs
        </div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Cada CV que preparas se guarda aquí, con un nombre por empresa y puesto (
          <code className="font-mono">Nombre__Empresa__Puesto__idioma.pdf</code>).
        </div>
        {cvLib && (
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-md bg-secondary px-2 py-1.5 font-mono text-[0.72rem] whitespace-nowrap">
              {cvLib.dir}
            </code>
            <span className="text-[0.72rem] whitespace-nowrap text-muted-foreground">
              {cvLib.count} {cvLib.count === 1 ? "archivo" : "archivos"}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                await copy(cvLib.dir);
                toast.success("Ruta copiada");
              }}
            >
              <Copy className="size-3.5" /> Copiar ruta
            </Button>
          </div>
        )}
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 text-sm font-semibold">Diseño del CSV</div>
        <div className="mb-3 text-[0.75rem] text-muted-foreground">
          Elige las columnas (el orden de selección es el orden del CSV).
        </div>
        <div className="mb-4 grid grid-cols-2 gap-2">
          {(columnsQ.data?.available ?? []).map((c) => (
            <Label key={c.id} className="cursor-pointer font-normal">
              <Checkbox checked={selected.includes(c.id)} onCheckedChange={() => toggleColumn(c.id)} />
              {c.label}
            </Label>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={saveColumns}>
            Guardar diseño
          </Button>
          <a className={buttonVariants()} href={api.exportUrl(selected)}>
            <Download className="size-4" /> Descargar CSV
          </a>
        </div>
      </section>
    </div>
  );
}
```

Nota: los botones pasan de "Guardar" (ambiguo x2 en el modal) a "Guardar nombre" / "Guardar carpeta" — mejora UX §4.3 sin lógica nueva; los tests usan esos nombres.

- [ ] **Step 4: Cablear la ruta y el sidebar; borrar el modal**

En `src/routes.tsx`, añadir dentro de `children` (después de `portfolio`):

```tsx
{ path: "settings", element: <SettingsPage /> },
```

con su import `import { SettingsPage } from "./pages/SettingsPage";`.

En `AppShell.tsx`:
- Eliminar `import { SettingsModal } from "./SettingsModal";`, el estado `settingsOpen` y el `<SettingsModal … />`.
- Reemplazar el `<button>` "Ajustes" del sidebar por un `NavLink` idéntico a los de `NAV` (mismo classname callback) con `to="/settings"`, icono `SettingsIcon` y label `Ajustes`.

Borrar el archivo:

```bash
git rm dashboard/frontend/src/components/SettingsModal.tsx
```

- [ ] **Step 5: Correr tests y verlos pasar**

Run: `npm --prefix dashboard/frontend test -- src/pages/SettingsPage.test.tsx src/components/AppShell.test.tsx`
Expected: PASS.

- [ ] **Step 6: Verificación completa + commit**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run build`
Expected: PASS.

```bash
git add dashboard/frontend/src/pages/SettingsPage.tsx dashboard/frontend/src/pages/SettingsPage.test.tsx dashboard/frontend/src/routes.tsx dashboard/frontend/src/components/AppShell.tsx
git commit -m "feat(settings): /settings como página — absorbe y elimina SettingsModal

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Extraer los subcomponentes del DetailDrawer a `job-detail/`

**Files:**
- Create: `dashboard/frontend/src/components/job-detail/SectionTitle.tsx`
- Create: `dashboard/frontend/src/components/job-detail/Ledger.tsx`
- Create: `dashboard/frontend/src/components/job-detail/MessageCard.tsx`
- Create: `dashboard/frontend/src/components/job-detail/SocialSearch.tsx`
- Create: `dashboard/frontend/src/components/job-detail/RecordOutcome.tsx`
- Create: `dashboard/frontend/src/components/job-detail/CompanyInsights.tsx`
- Create: `dashboard/frontend/src/components/job-detail/JobOverview.tsx`
- Modify: `dashboard/frontend/src/components/DetailDrawer.tsx` (borrar los bloques movidos, importar de `job-detail/`)

**Interfaces:**
- Consumes: `DetailDrawer.tsx` actual (los rangos de líneas citados abajo son del archivo en `master` de hoy; verificarlos con el archivo real antes de cortar), tipos de `src/api.ts` (`JobDetail`, `Learning`, `SocialMention`).
- Produces (firmas exactas que la Task 8 compone en tabs):

```ts
export function SectionTitle({ children }: { children: ReactNode }): JSX.Element;
export function Ledger({ d }: { d: JobDetail }): JSX.Element;
export function MessageCard({ m }: { m: JobDetail["messages"][number] }): JSX.Element;
export function SocialSearch({ jobId }: { jobId: string }): JSX.Element;
export function RecordOutcome({ jobId, onSaved }: { jobId: string; onSaved: () => void }): JSX.Element;
export function CompanyInsights({ learnings }: { learnings?: Learning[] }): JSX.Element | null;
export function JobOverview({ job }: { job: JobDetail["job"] }): JSX.Element;
```

Movimiento **verbatim** (misma JSX, mismos handlers); lo único que cambia son imports/exports. Este task es mecánico: el gate es que `DetailDrawer.test.tsx` siga verde sin tocarlo.

- [ ] **Step 1: `SectionTitle.tsx`** (origen: DetailDrawer.tsx:60-62)

```tsx
import type { ReactNode } from "react";

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="mb-2 text-caption text-muted-foreground uppercase">{children}</div>;
}
```

- [ ] **Step 2: `Ledger.tsx`** (origen: 64-105) — cuerpo verbatim, con este header y `export`:

```tsx
import { Check } from "lucide-react";
import type { JobDetail } from "../../api";
import { pct } from "../../lib";
import { Card } from "../ui/card";

export function Ledger({ d }: { d: JobDetail }) {
  // …líneas 65-104 del DetailDrawer actual, sin cambios…
}
```

- [ ] **Step 3: `MessageCard.tsx`** (origen: 49-58 `KIND_ES` + 107-153) — mover `KIND_ES` aquí (es su único consumidor junto a Task 8, que lo importa de aquí si lo necesita):

```tsx
import { Check, Copy, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type JobDetail } from "../../api";
import { copy } from "../../lib";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

export const KIND_ES: Record<string, string> = {
  cover_letter: "Carta de presentación",
  cold_email: "Email en frío",
  recruiter: "Mensaje a reclutador",
  hiring_manager: "Mensaje a hiring manager",
  referral_ask: "Pedido de referido",
  linkedin_note: "Nota de LinkedIn",
  follow_up: "Follow-up",
  breakup: "Cierre cordial",
};

export function MessageCard({ m }: { m: JobDetail["messages"][number] }) {
  // …líneas 108-153 del DetailDrawer actual, sin cambios…
}
```

- [ ] **Step 4: `SocialSearch.tsx`** (origen: 155-269, comentario incluido) — header:

```tsx
import { Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type SocialMention } from "../../api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Separator } from "../ui/separator";
import { SectionTitle } from "./SectionTitle";
```

Cuerpo verbatim (incluye su `useEffect` con el eslint-disable existente).

- [ ] **Step 5: `RecordOutcome.tsx`** (origen: 271-334) — header:

```tsx
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../../api";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { SectionTitle } from "./SectionTitle";
```

- [ ] **Step 6: `CompanyInsights.tsx`** (origen: 336-357) —

```tsx
import type { Learning } from "../../api";
import { Card } from "../ui/card";
import { InsightsIcon } from "../ui/icons";
import { SectionTitle } from "./SectionTitle";

export function CompanyInsights({ learnings }: { learnings?: Learning[] }) {
  // …líneas 337-357 verbatim…
}
```

- [ ] **Step 7: `JobOverview.tsx`** (origen: 359-487 — `InfoItem` incluido como helper privado del archivo) — header:

```tsx
import {
  Briefcase,
  CalendarClock,
  FileText,
  Globe,
  Languages,
  ListChecks,
  MapPin,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { JobDetail } from "../../api";
import { countryLabel, freshLabel, langLabel, salaryLabel, stripHtml, workplaceLabel } from "../../lib";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
```

(`InfoItem` cambia `icon: React.ReactNode` → `icon: ReactNode`, igual para `value`; no se exporta.)

- [ ] **Step 8: Adelgazar `DetailDrawer.tsx`**

Borrar de `DetailDrawer.tsx` los bloques movidos (líneas 49-487) y añadir:

```tsx
import { CompanyInsights } from "./job-detail/CompanyInsights";
import { JobOverview } from "./job-detail/JobOverview";
import { Ledger } from "./job-detail/Ledger";
import { MessageCard } from "./job-detail/MessageCard";
import { RecordOutcome } from "./job-detail/RecordOutcome";
import { SectionTitle } from "./job-detail/SectionTitle";
import { SocialSearch } from "./job-detail/SocialSearch";
```

Limpiar los imports que quedaron sin uso en DetailDrawer (lint `--max-warnings 0` los detecta: `Briefcase`, `CalendarClock`, `Check`, `Copy`, `Globe`, `Languages`, `ListChecks`, `MapPin`, `Plus`, `Search`, `Send`, `Wallet`, `Badge`?, etc. — dejar exactamente los que el JSX restante usa).

- [ ] **Step 9: Verificar que la suite existente sigue verde (el gate del task)**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test -- src/components/DetailDrawer.test.tsx`
Expected: PASS — mismos 5 tests del drawer, sin editar el test. Después la suite completa: `npm --prefix dashboard/frontend test` → PASS.

- [ ] **Step 10: Commit**

```bash
git add dashboard/frontend/src/components/job-detail/SectionTitle.tsx dashboard/frontend/src/components/job-detail/Ledger.tsx dashboard/frontend/src/components/job-detail/MessageCard.tsx dashboard/frontend/src/components/job-detail/SocialSearch.tsx dashboard/frontend/src/components/job-detail/RecordOutcome.tsx dashboard/frontend/src/components/job-detail/CompanyInsights.tsx dashboard/frontend/src/components/job-detail/JobOverview.tsx dashboard/frontend/src/components/DetailDrawer.tsx
git commit -m "refactor(detail): extraer subcomponentes del DetailDrawer a job-detail/ (sin cambios de comportamiento)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: JobDetailPage `/jobs/:id` con tabs + transparencia de score (borra DetailDrawer)

**Files:**
- Create: `dashboard/frontend/src/components/job-detail/ScoreBreakdown.tsx`
- Test: `dashboard/frontend/src/components/job-detail/ScoreBreakdown.test.tsx`
- Create: `dashboard/frontend/src/pages/JobDetailPage.tsx`
- Test: `dashboard/frontend/src/pages/JobDetailPage.test.tsx` (migra `DetailDrawer.test.tsx`)
- Modify: `dashboard/frontend/src/routes.tsx` (ruta `jobs/:id` → `JobDetailPage`)
- Modify: `dashboard/frontend/src/pages/PipelinePage.tsx` (borrar `JobDetailRoute` y su import de DetailDrawer)
- Delete: `dashboard/frontend/src/components/DetailDrawer.tsx`, `dashboard/frontend/src/components/DetailDrawer.test.tsx`

**Interfaces:**
- Consumes: componentes de Task 7 (firmas exactas de su bloque Produces), hooks `useJob(id?)`, `usePrepJob()`, `useMarkApplied()`, `useSetJobState()` (Task 3), `InterviewPanel({ jobId }: { jobId: string })` existente, `api.cvDownload(jobId, vid, fmt)`, `api.cvLibrary()`, `buttonVariants` de `ui/button`, `fitTone` v2 (Task 2), helpers `STATE_ES`, `copy`, `pct`, `salaryLabel`, `freshLabel`, `langLabel` de `src/lib`.
- Produces:
  - `export function ScoreBreakdown({ job }: { job: Job }): JSX.Element | null` — desglose "Por qué N" desde `job.fit_score` + `job.fit_reasons` + `job.knockout_flags` (la API ya los devuelve; cero backend).
  - `export function JobDetailPage(): JSX.Element` — página completa con tabs `Resumen | CV | Mensajes | Entrevistas | Research` (Radix Tabs values: `resumen`, `cv`, `mensajes`, `entrevistas`, `research`) y barra de acciones fija (Descartar / Marcar como aplicado / Re-preparar). Las Fases 2-4 añaden tabs/secciones aquí.

- [ ] **Step 1: Test del ScoreBreakdown (falla)**

Crear `dashboard/frontend/src/components/job-detail/ScoreBreakdown.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Job } from "../../api";
import { ScoreBreakdown } from "./ScoreBreakdown";

const base: Job = { id: "j1", title: "DS", company: "Acme", state: "shortlisted" };

describe("ScoreBreakdown", () => {
  it("muestra 'Por qué N' con razones y knockouts", () => {
    render(
      <ScoreBreakdown
        job={{
          ...base,
          fit_score: 74,
          fit_reasons: ["seniority match: senior", "remoto: sí"],
          knockout_flags: ["pide autorización de trabajo en US"],
        }}
      />,
    );
    expect(screen.getByText(/Por qué 74/)).toBeInTheDocument();
    expect(screen.getByText("seniority match: senior")).toBeInTheDocument();
    expect(screen.getByText("pide autorización de trabajo en US")).toBeInTheDocument();
  });

  it("sin score ni factores no renderiza nada", () => {
    const { container } = render(<ScoreBreakdown job={base} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("con score pero sin factores explica cómo recalcular", () => {
    render(<ScoreBreakdown job={{ ...base, fit_score: 60 }} />);
    expect(screen.getByText(/Por qué 60/)).toBeInTheDocument();
    expect(screen.getByText(/vuelve a correr “Buscar”/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correrlo y verlo fallar**

Run: `npm --prefix dashboard/frontend test -- src/components/job-detail/ScoreBreakdown.test.tsx`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar `ScoreBreakdown.tsx`**

```tsx
import { Check } from "lucide-react";
import type { Job } from "../../api";
import { Card } from "../ui/card";
import { KnockoutIcon } from "../ui/icons";

// §4.3 spec v2: transparencia de score — render legible de los factores que
// score_job ya produce (fit_reasons + knockout_flags). Sin lógica nueva.
export function ScoreBreakdown({ job }: { job: Job }) {
  const reasons = job.fit_reasons ?? [];
  const knockouts = job.knockout_flags ?? [];
  if (job.fit_score == null && reasons.length === 0 && knockouts.length === 0) return null;
  return (
    <Card className="p-3.5 text-sm">
      <div className="mb-2 text-caption text-muted-foreground uppercase">
        Por qué {job.fit_score ?? "—"}
      </div>
      {reasons.length === 0 && knockouts.length === 0 ? (
        <div className="text-muted-foreground">
          Esta vacante aún no tiene desglose guardado — vuelve a correr “Buscar” para recalcularlo.
        </div>
      ) : (
        <ul className="space-y-1.5">
          {reasons.map((r) => (
            <li key={r} className="flex items-start gap-2">
              <Check className="mt-0.5 size-3.5 shrink-0 text-success" strokeWidth={3} />
              <span>{r}</span>
            </li>
          ))}
          {knockouts.map((k) => (
            <li key={k} className="flex items-start gap-2 text-warning">
              <KnockoutIcon className="mt-0.5 size-3.5 shrink-0" />
              <span>{k}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Correrlo y verlo pasar**

Run: `npm --prefix dashboard/frontend test -- src/components/job-detail/ScoreBreakdown.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Migrar el test del drawer a la página (falla)**

Crear `dashboard/frontend/src/pages/JobDetailPage.test.tsx` — conserva las 5 aserciones de `DetailDrawer.test.tsx` (mismos mocks) + tabs + transparencia:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { toast, api } = vi.hoisted(() => ({
  toast: { loading: vi.fn(() => "tid"), success: vi.fn(), error: vi.fn() },
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    job: vi.fn(),
    prep: vi.fn(),
    markApplied: vi.fn(),
    setState: vi.fn(() => Promise.resolve({})),
    markSent: vi.fn(() => Promise.resolve({})),
    cvDownload: vi.fn(() => "/api/cv/job-1/1/download?fmt=pdf"),
    cvLibrary: vi.fn(() => Promise.resolve({ dir: "/cv", count: 0, files: [] })),
    socialMentions: vi.fn(() => Promise.resolve({ mentions: [] })),
    startSocialSearch: vi.fn(() => Promise.resolve({ ok: true, queries: {} })),
    addSocialMention: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    interviews: vi.fn(() => Promise.resolve({ interviews: [] })),
    addInterview: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    addInterviewer: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    genPrep: vi.fn(() => Promise.resolve({ ok: true, path: "", markdown: "" })),
    recordOutcome: vi.fn(() => Promise.resolve({ ok: true, learnings: [] })),
  },
}));
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

function jobDetail() {
  return {
    job: {
      id: "job-1",
      title: "Senior Data Scientist",
      company: "Acme",
      state: "shortlisted",
      fit_score: 90,
      fit_reasons: ["seniority match: senior"],
      knockout_flags: [],
      is_remote: 1,
      workplace_type: "remote",
      location: "Remote · United States",
      description: "Build models. Run A/B tests.",
      jd_skills: ["python", "sql"],
      language: "en",
      posted_days: 1,
    },
    cv_versions: [
      { id: 1, language: "en", path_pdf: "a", path_docx: "b", keyword_coverage: 0.6, parse_ok: 1 },
    ],
    messages: [],
    referrals: [],
    learnings: [],
    social_mentions: [],
    timeline: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: true,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.overview.mockResolvedValue({
    overview: {
      total_jobs: 1,
      counts: {},
      funnel: [],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
    },
    needs_action: [],
  });
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
  api.job.mockResolvedValue(jobDetail());
  api.prep.mockResolvedValue({ ok: true, coverage: 0.6, parse_ok: true, language: "en" });
  api.markApplied.mockResolvedValue({ ok: true });
});

describe("JobDetailPage — página /jobs/:id con tabs", () => {
  it("carga el detalle (título, tabs, descripción y skills en Resumen)", async () => {
    renderRoutes("/jobs/job-1");
    expect(await screen.findByText("Senior Data Scientist")).toBeInTheDocument();
    for (const tab of ["Resumen", "CV", "Mensajes", "Entrevistas", "Research"]) {
      expect(screen.getByRole("tab", { name: tab })).toBeInTheDocument();
    }
    expect(screen.getByText(/Build models/)).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
  });

  it("muestra la transparencia de score (Por qué 90 + razones)", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    expect(screen.getByText(/Por qué 90/)).toBeInTheDocument();
    expect(screen.getByText("seniority match: senior")).toBeInTheDocument();
  });

  it("Re-preparar llama api.prep y muestra toast de éxito", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Re-preparar/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1", undefined));
    expect(toast.loading).toHaveBeenCalled();
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it("Marcar como aplicado llama api.markApplied y toastea", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Marcar como aplicado/ }));
    await waitFor(() => expect(api.markApplied).toHaveBeenCalledWith("job-1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("Descartar pasa el job a dismissed y vuelve al pipeline", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(api.setState).toHaveBeenCalledWith("job-1", "dismissed"));
  });

  it("el tab CV tiene el link real de descarga del PDF", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "CV" }));
    const pdf = await screen.findByRole("link", { name: /CV PDF/ });
    expect(pdf.getAttribute("href")).toMatch(/\/api\/cv\/job-1\/1\/download\?fmt=pdf/);
  });

  it("el tab Mensajes ofrece generar borradores cuando no hay mensajes", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Mensajes" }));
    await userEvent.click(await screen.findByRole("button", { name: /Generar borradores/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1", undefined));
  });
});
```

- [ ] **Step 6: Correrlo y verlo fallar**

Run: `npm --prefix dashboard/frontend test -- src/pages/JobDetailPage.test.tsx`
Expected: FAIL — `/jobs/job-1` renderiza el `JobDetailRoute` temporal (drawer), no hay tabs.

- [ ] **Step 7: Implementar `JobDetailPage.tsx`**

```tsx
import {
  ArrowLeft,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  Loader2,
  Trash2,
} from "lucide-react";
import type * as React from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { api } from "../api";
import { CompanyInsights } from "../components/job-detail/CompanyInsights";
import { JobOverview } from "../components/job-detail/JobOverview";
import { Ledger } from "../components/job-detail/Ledger";
import { MessageCard } from "../components/job-detail/MessageCard";
import { RecordOutcome } from "../components/job-detail/RecordOutcome";
import { ScoreBreakdown } from "../components/job-detail/ScoreBreakdown";
import { SectionTitle } from "../components/job-detail/SectionTitle";
import { SocialSearch } from "../components/job-detail/SocialSearch";
import { InterviewPanel } from "../components/InterviewPanel";
import { Badge } from "../components/ui/badge";
import { Button, buttonVariants } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { MatchIcon, ReferralIcon, SalaryIcon } from "../components/ui/icons";
import { ScoreRing } from "../components/ui/score-ring";
import { Skeleton } from "../components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "../components/ui/tooltip";
import { useJob, useMarkApplied, usePrepJob } from "../hooks/useJob";
import { useSetJobState } from "../hooks/useBoard";
import { STATE_ES, copy, fitTone, freshLabel, langLabel, pct, salaryLabel } from "../lib";

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobQ = useJob(id);
  const prep = usePrepJob();
  const markApplied = useMarkApplied();
  const setJobState = useSetJobState();

  if (jobQ.isPending) {
    return (
      <div className="mx-auto max-w-[860px] space-y-4">
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (jobQ.isError || !jobQ.data) {
    return (
      <div className="mx-auto max-w-[860px] py-10 text-center text-sm text-muted-foreground">
        No se pudo cargar la vacante.{" "}
        <button type="button" className="text-primary hover:underline" onClick={() => jobQ.refetch()}>
          Reintentar
        </button>
      </div>
    );
  }

  const d = jobQ.data;
  const jobId = d.job.id;

  function doPrep() {
    if (prep.isPending) return;
    const tid = toast.loading("Preparando tu CV y mensajes…", {
      description: "Adapto el CV a esta oferta (ATS-safe) y redacto los mensajes.",
    });
    prep.mutate(
      { id: jobId },
      {
        onSuccess: (r) =>
          toast.success("CV y mensajes listos", {
            id: tid,
            description: `Cobertura ${pct(r.coverage)} · ${r.parse_ok ? "ATS ✓" : "revisar formato"}`,
          }),
        onError: () =>
          toast.error("No se pudo preparar", { id: tid, description: "Reintenta en un momento." }),
      },
    );
  }

  function doMarkApplied() {
    if (markApplied.isPending) return;
    markApplied.mutate(jobId, {
      onSuccess: () => toast.success("Marcado como aplicado"),
      onError: () => toast.error("No se pudo marcar como aplicado"),
    });
  }

  function doDismiss() {
    const prev = d.job.state || "shortlisted";
    setJobState.mutate(
      { id: jobId, state: "dismissed" },
      {
        onSuccess: () => {
          toast.success("Vacante descartada", {
            description: "No volverá a aparecer en tu tablero.",
            action: {
              label: "Deshacer",
              onClick: () => setJobState.mutate({ id: jobId, state: prev }),
            },
          });
          navigate("/pipeline");
        },
      },
    );
  }

  const cv = d.cv_versions[0];

  return (
    <div className="mx-auto max-w-[860px]">
      {/* header */}
      <button
        type="button"
        onClick={() => navigate("/pipeline")}
        className="mb-3 inline-flex items-center gap-1.5 text-[0.8rem] text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Volver al pipeline
      </button>
      <div className="flex items-start gap-3">
        <ScoreRing value={d.job.fit_score} tone={fitTone(d.job.fit_score)} />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-h1">{d.job.title}</h1>
          <div className="text-sm text-muted-foreground">{d.job.company}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {d.job.match_score != null && (
          <Badge
            variant="score"
            style={{ "--tone": fitTone(d.job.match_score) } as React.CSSProperties}
            title="Match CV↔oferta: cobertura ponderada de las keywords de la vacante"
          >
            match {d.job.match_score}%
          </Badge>
        )}
        <Badge variant="secondary">{STATE_ES[d.job.state] || d.job.state}</Badge>
        {d.job.is_remote === 1 && <Badge variant="secondary">Remoto</Badge>}
        {salaryLabel(d.job) && (
          <Badge variant="secondary" title="Salario publicado">
            <SalaryIcon /> {salaryLabel(d.job)}
          </Badge>
        )}
        {d.job.language && (
          <Badge variant="secondary" className="uppercase">
            {langLabel(d.job.language)}
          </Badge>
        )}
        {(d.job.posted_days ?? d.job.age_days) != null && (
          <Badge variant="secondary">{freshLabel(d.job.posted_days ?? d.job.age_days)}</Badge>
        )}
        {(d.job.apply_url || d.job.url) && (
          <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
            <a href={d.job.apply_url || d.job.url} target="_blank" rel="noreferrer">
              <ExternalLink className="size-3.5" /> Abrir oferta
            </a>
          </Button>
        )}
      </div>

      {/* tabs */}
      <Tabs defaultValue="resumen" className="mt-4">
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="cv">CV</TabsTrigger>
          <TabsTrigger value="mensajes">Mensajes</TabsTrigger>
          <TabsTrigger value="entrevistas">Entrevistas</TabsTrigger>
          <TabsTrigger value="research">Research</TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="mt-4 space-y-4">
          <ScoreBreakdown job={d.job} />
          <JobOverview job={d.job} />
          {d.job.missing_keywords && d.job.missing_keywords.length > 0 && (
            <Card className="p-3.5 text-sm">
              <div className="mb-2 flex items-center gap-1.5 font-medium">
                <MatchIcon className="size-4 text-muted-foreground" /> Keywords de la oferta que tu
                CV no evidencia
              </div>
              <div className="flex flex-wrap gap-1.5">
                {d.job.missing_keywords.slice(0, 12).map((k) => (
                  <Badge key={k} variant="outline">
                    {k}
                  </Badge>
                ))}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                Agrégalas a tu CV solo si realmente las tienes (nunca inventes).
              </div>
            </Card>
          )}
          <Ledger d={d} />
          {d.referrals.length > 0 && (
            <Card className="border-[color-mix(in_oklch,var(--accent2)_50%,var(--border))] bg-[color-mix(in_oklch,var(--accent2)_8%,transparent)] p-3.5">
              <div
                className="flex items-center gap-1.5 text-sm font-medium"
                style={{ color: "var(--accent2)" }}
              >
                <ReferralIcon className="size-4" /> Referido disponible (prioriza esto)
              </div>
              {d.referrals.map((r) => (
                <div key={r.id} className="mt-1 text-sm">
                  <b>{r.name}</b> — {r.title || ""} @ {r.company}
                  {r.linkedin_url && (
                    <a
                      href={r.linkedin_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-2 text-xs text-primary hover:underline"
                    >
                      LinkedIn ↗
                    </a>
                  )}
                </div>
              ))}
            </Card>
          )}
          <CompanyInsights learnings={d.learnings} />
        </TabsContent>

        <TabsContent value="cv" className="mt-4 space-y-4">
          {cv ? (
            <div className="space-y-1.5">
              <div className="text-sm text-muted-foreground">
                Cobertura {pct(cv.keyword_coverage)} · {cv.parse_ok ? "ATS ✓" : "revisar formato"}
              </div>
              <div className="flex gap-2">
                {cv.path_pdf && (
                  <a
                    href={api.cvDownload(jobId, cv.id, "pdf")}
                    className={buttonVariants({ className: "flex-1" })}
                  >
                    <FileText className="size-4" /> CV PDF <Download className="size-3.5" />
                  </a>
                )}
                <a
                  href={api.cvDownload(jobId, cv.id, "docx")}
                  className={buttonVariants({ variant: "secondary", className: "flex-1" })}
                >
                  <FileText className="size-4" /> CV DOCX <Download className="size-3.5" />
                </a>
              </div>
              <button
                type="button"
                onClick={async () => {
                  const l = await api.cvLibrary();
                  await copy(l.dir);
                  toast.success("Ruta de tu carpeta de CVs copiada", { description: l.dir });
                }}
                className="flex items-center gap-1.5 text-[0.72rem] text-muted-foreground transition-colors hover:text-foreground"
              >
                <FolderOpen className="size-3.5" /> También se guarda en tu carpeta de CVs (por
                empresa) · copiar ruta
              </button>
            </div>
          ) : (
            <Card className="p-4 text-sm text-muted-foreground">
              Aún no hay CV adaptado para esta oferta — usa “Re-preparar” (abajo) para generarlo.
            </Card>
          )}
        </TabsContent>

        <TabsContent value="mensajes" className="mt-4">
          <SectionTitle>Mensajes — qué enviar</SectionTitle>
          <div className="space-y-2">
            {d.messages.length === 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="secondary"
                    className="w-full"
                    onClick={doPrep}
                    disabled={prep.isPending}
                  >
                    {prep.isPending && <Loader2 className="size-4 animate-spin" />}
                    {prep.isPending ? "Generando…" : "Generar borradores"}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Adapta tu CV a esta oferta (ATS-safe) y redacta los mensajes de contacto.
                  Reordena solo lo que ya está en tu CV — nunca inventa. Determinista, sin IA.
                </TooltipContent>
              </Tooltip>
            )}
            {d.messages.map((m) => (
              <MessageCard key={m.id} m={m} />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="entrevistas" className="mt-4">
          <InterviewPanel jobId={jobId} />
        </TabsContent>

        <TabsContent value="research" className="mt-4 space-y-4">
          <SocialSearch jobId={jobId} />
          <RecordOutcome jobId={jobId} onSaved={() => jobQ.refetch()} />
        </TabsContent>
      </Tabs>

      {/* barra de acciones */}
      <div className="sticky bottom-0 z-10 mt-6 flex gap-2 border-t border-border bg-background/85 py-3 backdrop-blur-xl">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={doDismiss} aria-label="Descartar">
              <Trash2 className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Descartar — no me interesa (se puede deshacer)</TooltipContent>
        </Tooltip>
        <Button
          variant="secondary"
          className="flex-1"
          onClick={doMarkApplied}
          disabled={markApplied.isPending}
        >
          {markApplied.isPending && <Loader2 className="size-4 animate-spin" />}
          {markApplied.isPending ? "Marcando…" : "Marcar como aplicado"}
        </Button>
        <Button className="flex-1" onClick={doPrep} disabled={prep.isPending}>
          {prep.isPending && <Loader2 className="size-4 animate-spin" />}
          {prep.isPending ? "Preparando…" : "Re-preparar"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Cablear ruta y borrar el drawer**

En `src/routes.tsx`: eliminar `import { JobDetailRoute } from "./pages/PipelinePage";`, añadir `import { JobDetailPage } from "./pages/JobDetailPage";` y cambiar la ruta a `{ path: "jobs/:id", element: <JobDetailPage /> }`.

En `src/pages/PipelinePage.tsx`: borrar el componente `JobDetailRoute` completo y los imports que solo él usaba (`useParams`, `useQueryClient`, `DetailDrawer`).

```bash
git rm dashboard/frontend/src/components/DetailDrawer.tsx dashboard/frontend/src/components/DetailDrawer.test.tsx
```

- [ ] **Step 9: Correr los tests y verlos pasar**

Run: `npm --prefix dashboard/frontend test -- src/pages/JobDetailPage.test.tsx src/components/job-detail/ScoreBreakdown.test.tsx`
Expected: PASS (10 tests).

- [ ] **Step 10: Verificación completa + QA visual**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run build`
Expected: PASS. QA con preview tools: abrir una card → página de detalle; recorrer los 5 tabs; probar Re-preparar y Descartar (con Deshacer); URL compartible `/jobs/<id>` recargable (backend Task 4).

- [ ] **Step 11: Commit**

```bash
git add dashboard/frontend/src/pages/JobDetailPage.tsx dashboard/frontend/src/pages/JobDetailPage.test.tsx dashboard/frontend/src/components/job-detail/ScoreBreakdown.tsx dashboard/frontend/src/components/job-detail/ScoreBreakdown.test.tsx dashboard/frontend/src/routes.tsx dashboard/frontend/src/pages/PipelinePage.tsx
git commit -m "feat(detail): /jobs/:id como página con tabs + transparencia de score; adiós DetailDrawer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Estados vacíos/cargando/error consistentes + toasts unificados

**Files:**
- Create: `dashboard/frontend/src/components/ui/states.tsx`
- Test: `dashboard/frontend/src/components/ui/states.test.tsx`
- Modify: `dashboard/frontend/src/pages/PipelinePage.tsx` (skeleton inline → `LoadingState`; añadir `ErrorState`)
- Modify: `dashboard/frontend/src/pages/AnalyticsPage.tsx` (ídem)
- Modify: `dashboard/frontend/src/pages/SettingsPage.tsx` (ídem)
- Modify: `dashboard/frontend/src/pages/JobDetailPage.tsx` (error inline → `ErrorState`)
- Modify: `dashboard/frontend/src/pages/OnboardingPage.tsx` (skeleton → `LoadingState`)

**Interfaces:**
- Consumes: primitivos `Card`, `Skeleton`, `Button` (Task 2); queries con `isPending`/`isError`/`refetch` (Task 3).
- Produces (firmas exactas):

```ts
export function LoadingState({ rows?, className? }: { rows?: number; className?: string }): JSX.Element;
export function ErrorState({ title?, description?, onRetry }: { title?: string; description?: string; onRetry?: () => void }): JSX.Element;
export function EmptyState({ icon?, title, description?, action? }: { icon?: LucideIcon; title: string; description?: string; action?: ReactNode }): JSX.Element;
```

Convención de toasts (documentada en Task 10 y aplicada ya en Tasks 5-8): sonner único montado en AppShell; `toast.success` para confirmaciones, `toast.error` con `description` accionable para fallos, `toast.loading`+`id` para operaciones largas; toda acción destructiva ofrece `action: { label: "Deshacer" }`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `dashboard/frontend/src/components/ui/states.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, LoadingState } from "./states";

describe("states compartidos", () => {
  it("LoadingState pinta N filas skeleton", () => {
    const { container } = render(<LoadingState rows={4} />);
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(4);
  });

  it("ErrorState muestra mensaje accionable y dispara onRetry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    expect(screen.getByText("No se pudo cargar")).toBeInTheDocument();
    expect(screen.getByText(/scripts\/run\.sh/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("EmptyState muestra título, descripción y acción", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="Sin vacantes"
        description="Corre una búsqueda."
        action={<button type="button">Buscar</button>}
      />,
    );
    expect(screen.getByText("Sin vacantes")).toBeInTheDocument();
    expect(screen.getByText("Corre una búsqueda.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buscar" })).toBeInTheDocument();
  });
});
```

Nota: el `Skeleton` actual ya emite `data-slot="skeleton"` (patrón React-19 de los primitivos); si no lo hiciera, añadirlo en `skeleton.tsx` es parte de este step.

- [ ] **Step 2: Correrlos y verlos fallar**

Run: `npm --prefix dashboard/frontend test -- src/components/ui/states.test.tsx`
Expected: FAIL — módulo `./states` inexistente.

- [ ] **Step 3: Implementar `states.tsx`**

```tsx
import type { LucideIcon } from "lucide-react";
import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Card } from "./card";
import { Skeleton } from "./skeleton";

// Estados compartidos de página (spec v2 §4.3): skeletons y mensajes accionables
// consistentes en todas las vistas. Componer SIEMPRE estos, no ad-hoc.

export function LoadingState({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={i === 0 ? "h-24 w-full" : "h-16 w-full"} />
      ))}
    </div>
  );
}

export function ErrorState({
  title = "No se pudo cargar",
  description = "Revisa que el backend esté corriendo (scripts/run.sh) y reintenta.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="flex flex-col items-center gap-2 px-5 py-8 text-center">
      <div className="grid size-11 place-items-center rounded-full bg-destructive/15 text-destructive">
        <CircleAlert className="size-5" />
      </div>
      <div className="text-h3 font-semibold">{title}</div>
      <div className="max-w-[48ch] text-sm text-muted-foreground">{description}</div>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </Card>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center gap-1.5 px-5 py-8 text-center">
      {Icon && (
        <div className="grid size-11 place-items-center rounded-full bg-secondary text-muted-foreground">
          <Icon className="size-5" />
        </div>
      )}
      <div className="text-h3 font-semibold">{title}</div>
      {description && <div className="text-sm text-muted-foreground">{description}</div>}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `npm --prefix dashboard/frontend test -- src/components/ui/states.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Aplicar a las páginas**

En cada página, el patrón exacto (mismo orden de guards):

```tsx
if (xQ.isPending) return <LoadingState rows={3} />;
if (xQ.isError) return <ErrorState onRetry={() => xQ.refetch()} />;
```

- `PipelinePage.tsx`: reemplazar el bloque de skeletons inline por `if (boardQ.isPending || overviewQ.isPending) return <LoadingState rows={4} />;` y añadir `if (boardQ.isError) return <ErrorState onRetry={() => boardQ.refetch()} />;` justo después. Import: `import { ErrorState, LoadingState } from "../components/ui/states";` (retirar el import de `Skeleton` si queda sin uso).
- `AnalyticsPage.tsx`: ídem (`overviewQ`), y si `funnel` viene vacío con 0 jobs, renderizar debajo del strip `<EmptyState title="Sin datos todavía" description="Corre una búsqueda para poblar el embudo." />`.
- `SettingsPage.tsx`: reemplazar skeletons por `<LoadingState rows={3} className="mx-auto max-w-[640px]" />` + `ErrorState` si `settingsQ.isError`.
- `JobDetailPage.tsx`: reemplazar el div de error inline del Step 7 (Task 8) por `<ErrorState title="No se pudo cargar la vacante" onRetry={() => jobQ.refetch()} />`.
- `OnboardingPage.tsx`: `<LoadingState rows={2} className="mx-auto max-w-[760px]" />`.

- [ ] **Step 6: Test de regresión del error state en pipeline**

Añadir a `src/pages/PipelinePage.test.tsx`:

```tsx
it("si /api/board falla muestra ErrorState accionable", async () => {
  api.board.mockRejectedValue(new Error("500"));
  renderRoutes("/pipeline");
  expect(await screen.findByText("No se pudo cargar")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
});
```

Run: `npm --prefix dashboard/frontend test -- src/pages/PipelinePage.test.tsx`
Expected: PASS.

- [ ] **Step 7: Verificación completa + commit**

Run: `npm --prefix dashboard/frontend run lint && npm --prefix dashboard/frontend run format && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run build`
Expected: PASS.

```bash
git add dashboard/frontend/src/components/ui/states.tsx dashboard/frontend/src/components/ui/states.test.tsx dashboard/frontend/src/pages/PipelinePage.tsx dashboard/frontend/src/pages/PipelinePage.test.tsx dashboard/frontend/src/pages/AnalyticsPage.tsx dashboard/frontend/src/pages/SettingsPage.tsx dashboard/frontend/src/pages/JobDetailPage.tsx dashboard/frontend/src/pages/OnboardingPage.tsx dashboard/frontend/src/components/ui/skeleton.tsx
git commit -m "feat(ux): LoadingState/ErrorState/EmptyState compartidos + toasts unificados en todas las vistas

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: DESIGN_SYSTEM.md v2 + skill `atlas-design-system` actualizado

**Files:**
- Modify: `dashboard/frontend/DESIGN_SYSTEM.md` (reemplazo completo)
- Modify: `.claude/skills/atlas-design-system/SKILL.md` (reemplazo completo)

**Interfaces:**
- Consumes: nombres/valores finales de tokens (Task 1), primitivos restyleados (Task 2), rutas/hooks/estados (Tasks 3-9), visual-language doc (nombre de la dirección estética y descripciones de paleta).
- Produces: la documentación vinculante que futuras sesiones (y las Fases 2-4) leerán ANTES de tocar UI. Si esto no se actualiza, el skill re-aplicaría Warm Editorial (riesgo señalado en la spec §4.1).

- [ ] **Step 1: Reescribir `dashboard/frontend/DESIGN_SYSTEM.md`**

Contenido completo (las celdas de descripción de paleta se completan con los nombres de color del visual-language doc):

```markdown
# Atlas Design System v2

Spec visual vinculante del dashboard (`dashboard/frontend/`). **Todo cambio de UI la sigue.**
Se aplica en dos capas: tokens/primitivos canónicos en código (`src/index.css` +
`src/components/ui/*`) y el skill `.claude/skills/atlas-design-system/` que trae los cambios
de IA de vuelta aquí. La dirección estética, paleta y tipografía nacen de
`docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md` (mockups aprobados).

> **Regla de oro:** componer desde `src/components/ui/*` y los tokens semánticos.
> Nada de botones/inputs/badges a mano ni colores hex.

## 1. Filosofía

<dirección estética v2 — copiar el párrafo de intención del visual-language doc>.
Reemplaza al "Warm Editorial" v1 (charcoal cálido + ámbar/terracota): ese sistema está RETIRADO.

## 2. Arquitectura de la app (v2)

- **Router:** react-router v7 (modo librería, paquete `react-router`). Rutas:
  `/pipeline` (default) · `/jobs/:id` (detalle con tabs Resumen/CV/Mensajes/Entrevistas/Research)
  · `/analytics` · `/portfolio` · `/settings` · `/onboarding`. `/` y `*` redirigen a `/pipeline`.
- **Shell:** `src/components/AppShell.tsx` — sidebar (tokens `--sidebar*`) + header compacto +
  ⌘K (CommandPalette con grupo "Ir a"). Toaster/diálogos globales viven aquí, una sola vez.
- **Datos:** TanStack Query v5. Hooks por recurso en `src/hooks/` (keys centralizadas en
  `src/hooks/keys.ts`). Páginas NUNCA llaman `api.*` directo para leer, ni `useEffect`+`useState`
  para datos de servidor.
- **Estados:** `LoadingState` / `ErrorState` / `EmptyState` de `src/components/ui/states.tsx` en
  toda página. `toast.loading→success/error` con `id` para operaciones largas; acciones
  destructivas con `action: Deshacer`.

## 3. Theming — `[data-theme]`, nunca `.dark`

`data-theme="dark" | "light"` en `<html>`, aplicado pre-paint en `main.tsx` y gestionado por
`src/hooks/useTheme.ts`. Variant de Tailwind ya cableada en `index.css`:
`@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`
No introducir la clase `.dark` ni cambiar el mecanismo.

## 4. Tokens (`src/index.css`)

OKLCH en `:root` (dark, default) y `:root[data-theme="light"]`, expuestos vía `@theme inline`.
Usar utilities (`bg-card`, `text-muted-foreground`, `border-border`, `ring-ring`, `bg-sidebar`,
`bg-sidebar-active`, …) o `var(--token)` — nunca colores crudos.

| Token | Utility | Uso |
|---|---|---|
| `--background` / `--foreground` | `bg-background` / `text-foreground` | lienzo / texto |
| `--card` / `--card-foreground` | `bg-card` | cards, tarjetas del kanban |
| `--popover` / `--popover-foreground` | `bg-popover` | menús, diálogos, palette |
| `--primary` / `--primary-foreground` | `bg-primary` / `text-primary` | acento de marca, botón primario |
| `--accent2` | `var(--accent2)` | acento secundario (referidos, ask_referral) |
| `--secondary` / `--secondary-foreground` | `bg-secondary` | botones secundarios, hovers, chips |
| `--muted-foreground` | `text-muted-foreground` | captions, texto apagado |
| `--success/warning/info/destructive` (+`-foreground`) | `bg-*`/`text-*` | semánticos |
| `--border` / `--input` / `--ring` | `border-border` / `border-input` / `ring-ring` | líneas, campos, foco |
| `--sidebar`, `--sidebar-foreground`, `--sidebar-border`, `--sidebar-active`, `--sidebar-active-foreground` | `bg-sidebar` etc. | app shell |
| `--chart-1..5` | `bg-chart-N` | embudo y charts |
| `--shadow-xs/sm/md/lg`, `--highlight-top` | `shadow-[var(--…)]` | elevación |
| `--radius` (+ sm/md/lg/xl) | `rounded-*` | radios |
| `--ease-out/in-out`, `--dur-fast/base/slow` | `ease-[var(--…)]` | motion |

### ⚠️ Reglas de nombres
- `accent`, `accent-foreground` y la superficie `muted` NO están mapeadas: **nunca**
  `bg-accent` / `text-accent-foreground` / `bg-muted`. Hover/superficies → `secondary`;
  texto apagado → `text-muted-foreground`.
- El compat layer `--color-*` de v1 **ya no existe**. `fitTone()` y `ACTION_META` (en `src/lib`)
  devuelven `var(--success|primary|info|warning|accent2|muted-foreground)`.
- No escribir `*/` dentro de comentarios CSS en `index.css`.

## 5. Tipografía y motion

Familias: `--font-sans` / `--font-mono` (paquetes @fontsource-variable importados en `main.tsx`;
cuáles, en el visual-language doc). Escala: `text-display/h1/h2/h3/caption` (valores en
`index.css`). `tabular-nums` SIEMPRE en números vivos (scores, métricas, %, salarios, contadores).
Motion: `--ease-*` + `--dur-*`, entradas con `.fade-up`, Radix vía `tw-animate-css`; respeta
`prefers-reduced-motion`. **Nunca** animar el transform de un nodo dnd-kit ni poner
`backdrop-filter`/`filter` en un ancestro draggable.

## 6. Primitivos (`src/components/ui/`)

Mismos 22 archivos y APIs que v1 (Button, Badge, Card, Checkbox, Command, Dialog, DropdownMenu,
icons, Input, Kbd, Label, ScoreRing, ScrollArea, Select, Separator, Sheet, Skeleton, Sonner,
Switch, Tabs, Textarea, Tooltip) + `states.tsx` (LoadingState/ErrorState/EmptyState).
Variants de Button: `default/secondary/outline/ghost/destructive/link`; sizes
`sm/default/lg/icon/icon-sm`. Variants de Badge: `default/secondary/outline/success/warning/
info/destructive/score` (score lee `--tone` por style, con `fitTone()`).
Iconos: SOLO lucide; los de dominio se declaran en `ui/icons.ts` (no emoji crudo en la UI).
Select: contenido `z-[95]`, `position="popper"`, item value nunca `""`.

## 7. Verificar

```bash
npm --prefix dashboard/frontend run lint          # eslint --max-warnings 0
npm --prefix dashboard/frontend run format:check
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
./scripts/check.sh
```

QA visual: backend (`uv run uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8787`) +
`npm --prefix dashboard/frontend run dev`; revisar /pipeline, /jobs/:id (5 tabs), /analytics,
/portfolio, /settings, /onboarding y la palette en **ambos temas**.

## 8. Extender con shadcn

`components.json` sigue configurado. Se puede `npx shadcn@latest add <componente>`, pero
re-tematizar el archivo generado a los tokens v2 y revertir cualquier edición que la CLI haga a
`src/index.css`. Preferir escribir a mano en el estilo existente.
```

- [ ] **Step 2: Reescribir `.claude/skills/atlas-design-system/SKILL.md`**

Contenido completo:

```markdown
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
```

- [ ] **Step 3: Verificar que no queda referencia viva a Warm Editorial**

Run: `rtk proxy grep -rin "warm editorial" dashboard/frontend .claude/skills/atlas-design-system docs/superpowers/plans/2026-07-04-atlas-v2-f1-ui-foundations.md --include='*.md' --include='*.css' --include='*.tsx'`
Expected: matches solo como menciones históricas ("RETIRADO", spec/plan) — ninguna instrucción vigente que lo aplique.

- [ ] **Step 4: Commit**

```bash
git add dashboard/frontend/DESIGN_SYSTEM.md .claude/skills/atlas-design-system/SKILL.md
git commit -m "docs(design): DESIGN_SYSTEM.md v2 + skill atlas-design-system apuntando al sistema nuevo

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Gate final F1 — paridad funcional + suites + build + QA visual

**Files:**
- Ninguno nuevo (solo fixes que salgan del gate; cada fix se commitea aparte con su test).

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: F1 lista para `superpowers:finishing-a-development-branch` (abrir PR a `master` — decisión de merge del usuario; master protegido).

- [ ] **Step 1: Suites completas**

```bash
rtk uv run --group dev pytest
npm --prefix dashboard/frontend run lint
npm --prefix dashboard/frontend run format:check
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
```

Expected: TODO verde (backend 120+ tests con los 3 nuevos del SPA fallback; frontend con las suites nuevas de hooks/shell/páginas/estados).

- [ ] **Step 2: Builds y gate del repo**

```bash
npm --prefix dashboard/frontend run build
./scripts/check.sh
```

Expected: `vite build` OK y `✓ All checks passed.`

- [ ] **Step 3: Smoke servido por FastAPI (como en producción local)**

```bash
./scripts/run.sh 8787 &
sleep 3
rtk curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/pipeline      # → 200
rtk curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/jobs/abc      # → 200 (index.html)
rtk curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/api/nope      # → 404
kill %1
```

- [ ] **Step 4: Checklist de paridad funcional (QA con preview tools, dark y light)**

Con backend + dev server corriendo, verificar UNO a UNO (criterio de done F1 de la spec §4):

- [ ] **Buscar**: botón "Buscar" del header → banner de progreso con contador → toast "Búsqueda completa" → tablero refrescado. También desde ⌘K.
- [ ] **Kanban**: drag & drop entre columnas persiste (recargar la página y sigue); contador por columna; filtros (salario/idioma/frescura) filtran; descartar card → toast con Deshacer funcional; sección "Descartadas (N)" restaura.
- [ ] **Detalle**: click en card → URL `/jobs/<id>`; recarga directa de esa URL funciona (SPA fallback); 5 tabs completos; **ScoreBreakdown visible con razones/knockouts**; "Abrir oferta" abre el posting.
- [ ] **Aplicar**: "Re-preparar" genera CV+mensajes (toasts loading→success con cobertura); descargas PDF/DOCX responden; "Marcar como aplicado" mueve el estado.
- [ ] **Outcome**: tab Research → Registrar resultado guarda y refresca learnings.
- [ ] **Entrevistas**: tab Entrevistas → añadir entrevista + entrevistador + generar prep (igual que v1).
- [ ] **Portfolio**: `/portfolio` genera/preview del portafolio, peers y research; cambiar de perfil refresca la vista.
- [ ] **Export**: `/settings` → columnas CSV seleccionables, "Guardar diseño", "Descargar CSV" baja el archivo con esas columnas.
- [ ] **Settings**: renombrar perfil se refleja en el selector del header; carpeta de descarga persiste.
- [ ] **Onboarding**: con perfil incompleto todo redirige a `/onboarding`; completar → redirige a `/pipeline`.
- [ ] **Perfiles**: switch de perfil recarga tablero/overview/portfolio del perfil nuevo y navega a `/pipeline`.
- [ ] **⌘K**: grupo "Ir a" navega a las 4 vistas; buscar vacante abre su página; "Resumen del día" abre el diálogo de brief.
- [ ] **Tema**: toggle dark/light persiste tras recargar; sin flash (main.tsx pre-paint).
- [ ] **Responsive básico**: `preview_resize` a 1100×700 — sidebar colapsa a iconos (`max-lg:w-14`), el kanban scrollea horizontal, nada se rompe (objetivo laptop pequeña, no mobile).
- [ ] **Cero rastro v1**: nada ámbar/terracota, sin `shadow-glow`, sin Tabs Pipeline/Portafolio en el header.

- [ ] **Step 5: Registrar el resultado del gate**

Si TODO pasó: anotar en el PR body el checklist marcado. Si algo falló: fix con test de regresión + commit, y re-correr el step correspondiente (verification-before-completion: nada se declara done sin comando + salida vista).

- [ ] **Step 6: Cierre de rama**

Usar `superpowers:finishing-a-development-branch`: suite completa ya verde → opción **crear PR** hacia `master` (repo personal pero master protegido con PR; el merge lo decide el usuario). Título sugerido: `feat: Atlas v2 F1 — fundaciones UI/UX (design system v2 + router + TanStack Query)`.

---

## Notas de ejecución

- **Orden estricto:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11. (4 puede ir en paralelo con 2-3 si hay dos workers, pero SIEMPRE antes de la 5 para QA de deep links.)
- **Paridad ante todo:** cada task termina con la app usable y la suite verde; nunca hay un commit intermedio con una feature perdida (el DetailDrawer vive hasta que su reemplazo pasa tests).
- **Los rangos de línea citados** (App.tsx, DetailDrawer.tsx, main.py) corresponden al árbol actual del worktree; si otra task los movió, localizar el bloque por contenido antes de cortar.
- **Fases siguientes:** F2 (onboarding wizard + geo-scoring) añadirá pasos a `/onboarding` y campos a settings; F3 añade `/followups` y amplía `/analytics`; F4 añade el panel "Tareas del Brain" al AppShell. Las rutas/hook-conventions de este plan son su contrato.





