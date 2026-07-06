# Atlas v2 — Índice maestro de ejecución

**Spec:** [`../specs/2026-07-04-atlas-v2-design.md`](../specs/2026-07-04-atlas-v2-design.md)
**Fecha:** 2026-07-04 · **Estado:** planes escritos, aprobación del usuario pendiente

Rediseño de Atlas en 4 fases secuenciales. Cada fase es un plan independiente, ejecutable
task-por-task con `superpowers:subagent-driven-development`, y cierra como **un PR** sobre
`master` (repo personal, master protegido → PR sin auto-merge; el merge lo decide el usuario).

## Orden de ejecución (secuencial, no paralelo)

| # | Plan | Tareas | Qué entrega |
| --- | --- | --- | --- |
| **F1** | [f1-ui-foundations](2026-07-04-atlas-v2-f1-ui-foundations.md) | 11 | Nuevo design system (tokens OKLCH v2) + app multi-vista (react-router v7 + TanStack Query), detalle de job como página, transparencia de score, paridad funcional total. |
| **F2** | [f2-onboarding-geo-scoring](2026-07-04-atlas-v2-f2-onboarding-geo-scoring.md) | 16 | Onboarding wizard por perfil (país, CV, tipo de trabajo), **geo-scoring de remotos restringidos**, liveness gate, detección de reposts/ghost jobs, snapshots de postings. |
| **F3** | [f3-deterministic-features](2026-07-04-atlas-v2-f3-deterministic-features.md) | 13 | Follow-ups v2 (cadencia + auto-seed + buckets), analytics/funnel + loop de aprendizaje, story bank STAR+R, knock-out pre-scan, reverse ATS discovery, exponer CLI-only en la web. |
| **F4** | [f4-llm-intents](2026-07-04-atlas-v2-f4-llm-intents.md) | 14 | Cola de intents + guided handoff ("corre atlas"), reviewer de CV/carta, legitimidad de postings, upskill report, interview prep profundo, expand de perfil, verificación visual de PDF. |

**Prerrequisito de F1:** la propuesta visual aprobada en
`../specs/2026-07-04-atlas-v2-visual-language.md` (valores OKLCH de paleta + tipografía).
F1 la consume en su Task 1; **no arrancar F1 sin ese doc aprobado.**

## Principios transversales (todas las fases)

- **Doctrina $0:** el backend nunca llama a una API LLM. Lo determinista corre en el motor;
  lo que necesita juicio LLM lo ejecuta el *brain* (Claude Code) y la web solo lo encola.
- **Todo usable desde la web:** las features LLM se piden con botones que encolan un intent;
  el panel "Tareas del Brain" muestra la única frase a memorizar — *"Abre Claude Code en el
  repo de Atlas y di: `corre atlas`"*.
- **Repo público:** datos personales solo en SQLite/`profiles/` gitignorados; nunca en código,
  tests, fixtures ni docs. Prompts del brain sí se commitean.
- **TDD + commits atómicos** por nombre de archivo (nunca `git add .`); trailer
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Tests:** backend `rtk uv run --group dev pytest`; frontend `npm --prefix dashboard/frontend test`.

## Notas de integración cruzada (resolver en ejecución)

Los planes se escribieron en paralelo; estas tres costuras deben respetarse al ejecutar en
orden. No requieren reescribir tareas, solo conciencia del estado previo:

1. **`engine/scoring/fit.py` lo tocan F2 y F3.** F2 añade el factor geo (2c) y el
   geo-mismatch (2d); F3 (Task 10, "machine summary") añade el registro de deltas por factor
   en `score_job`. Como F3 se ejecuta **después** de F2 mergeado, el implementador de F3 ve la
   versión ya modificada por F2: los deltas del machine summary deben **incluir** los factores
   geo de F2. Si los números de línea del plan F3 no calzan, re-localizar por el nombre del
   factor, no por línea.

2. **Capa de datos frontend (`src/api.ts` + hooks).** F1 establece la convención: toda lectura
   de servidor en páginas nuevas pasa por hooks de `src/hooks/` (TanStack Query), no por
   `useState`+`fetch`. F2/F3/F4 añaden funciones a `api.ts` y vistas nuevas (`/onboarding`,
   `/followups`, `/upskill`, paneles de settings): **envolver esas llamadas en hooks** siguiendo
   el patrón de F1 (`qk` en `src/hooks/keys.ts`, mutaciones con invalidación), aunque el texto
   del plan de la fase muestre una llamada directa a `api.*` (se escribió contra el `api.ts`
   pre-F1).

3. **Rutas y navegación del sidebar.** F1 deja montadas `/pipeline`, `/jobs/:id`, `/analytics`,
   `/portfolio`, `/onboarding`, `/settings` (y reserva el slot `/followups` en el sidebar).
   F2 sustituye el contenido de `/onboarding` (wizard). F3 enriquece `/analytics` y añade el
   ítem de nav + ruta `/followups`. F4 añade el ítem + ruta `/upskill` y el panel "Tareas del
   Brain" en el app shell. Cada fase que añade una ruta debe registrarla en el router de F1
   (`src/routes.tsx`) y su ítem en el sidebar.

4. **Story bank (F3) ↔ interview prep profundo (F4).** F4 `interview_prep_deep` consume
   `match_stories()` de F3. F4 ya trae un import guardado (fallback) por si se ejecutara sin F3,
   pero el orden canónico (F3 antes que F4) hace que el matcher real esté disponible.

## Cierre de cada fase

`superpowers:finishing-a-development-branch` → verifica suites + `./scripts/check.sh` +
`npm --prefix dashboard/frontend run build` → abre PR (sin auto-merge). El merge a `master`
lo decide el usuario.
