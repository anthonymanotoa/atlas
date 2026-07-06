# Atlas v2 — Rediseño UI/UX, geo-scoring y features importadas (spec de diseño)

**Fecha:** 2026-07-04
**Estado:** aprobación pendiente del usuario
**Alcance:** 4 fases secuenciales, cada una un PR revisable sobre `master`.

## 1. Contexto y objetivos

Atlas es un job-search assistant personal: motor determinista en Python (FastAPI + SQLite,
$0 en LLM), dashboard React (Vite + Tailwind v4 + shadcn/Radix), y un "brain" LLM que corre
vía Claude Code/Cowork. Este proyecto lo evoluciona en tres frentes:

1. **UI/UX**: reemplazar por completo el sistema de diseño "Warm Editorial" (nueva dirección
   estética, nueva paleta) y re-arquitecturar la navegación a una app multi-vista con router.
2. **Scoring**: penalizar (sin filtrar) los trabajos remotos que exigen residir en un
   país/región distinto al del candidato.
3. **Features**: importar el mejor know-how de dos repos de referencia —
   [career-ops](https://github.com/santifer/career-ops) y
   [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) — y darles una pasada de
   mejora a las features existentes.

**Principio rector (decidido con el usuario):** todo debe ser usable desde la web UI sin
memorizar comandos. Lo que requiera LLM se ejecuta vía el brain (Claude Code), pero la web
lo encola y **explica exactamente qué decirle a Claude Code** (una sola frase universal).

## 2. Decisiones ya tomadas

| Tema | Decisión |
| --- | --- |
| Estética | Carta blanca para Claude; propuesta con mockups a aprobar **antes** de implementar la Fase 1. Nada parecido al Warm Editorial actual. |
| Navegación | App multi-vista con router (URLs reales, navegación lateral). |
| Onboarding | Wizard por perfil en la web: país, CV, tipo de trabajo, etc. **Nada hardcodeado** — cada candidato configura lo suyo. |
| Geo-penalización | Moderada (default −12, configurable), universal para todos los perfiles. Para el perfil de Anthony: país Ecuador. |
| Ejecución LLM | Sin API key en el backend (se mantiene la doctrina $0). Cola de intents + guided handoff: la web encola y muestra la instrucción exacta para Claude Code. |
| Estructura | 4 fases secuenciales, UI primero. Un solo spec maestro + plan por fases. |

## 3. Arquitectura objetivo (resumen)

```
React SPA (router + TanStack Query)          FastAPI (127.0.0.1:8787)
  /pipeline  /jobs/:id  /analytics    ──────►  /api/* (origin-guarded POSTs)
  /followups /interviews /upskill                │
  /portfolio /settings  /onboarding              ▼
                                              SQLite (WAL) ── tabla nueva: intents
                                                 ▲
Brain (Claude Code / Cowork, LLM) ───────────────┘
  1) drena intents pendientes  2) pipeline diario  3) escribe resultados en DB
```

- El **motor** (`engine/`) sigue determinista y $0: extracción geo, liveness, reposts,
  knock-outs, analytics y story-matcher son heurísticas sin LLM.
- El **brain** gana un paso 0: drenar la cola `intents` (reviewer de CV, legitimidad,
  upskill, prep profundo, expand de perfil). La web nunca bloquea esperando al LLM.
- **Guided handoff**: un panel "Tareas del Brain" en la web lista intents pendientes y
  muestra la única frase que hay que aprenderse: *"Abre Claude Code en el repo de Atlas y
  di: `corre atlas`"* (el `SKILL.md` del brain resuelve el resto). Cada botón LLM de la web
  explica qué va a pasar y cuándo estará el resultado.

## 4. Fase 1 — Fundaciones UI/UX (rediseño completo)

**Objetivo:** nueva identidad visual + nueva arquitectura de navegación, con paridad
funcional (ninguna feature se pierde; las únicas adiciones son las mejoras UX de §4.3,
que no introducen lógica de negocio nueva).

### 4.1 Sistema de diseño v2
- Dirección, paleta y tipografía: se definen en la **propuesta de mockups** (gate de
  aprobación previo a implementar). Restricción dura: distinto del Warm Editorial actual.
- Implementación: tokens OKLCH semánticos en `dashboard/frontend/src/index.css`
  (`@theme inline`, temas light+dark vía `data-theme`), primitivos en
  `src/components/ui/*` restyleados (se conservan las APIs de los 22 primitivos).
- Documentación: `dashboard/frontend/DESIGN_SYSTEM.md` v2 reemplaza al actual, y el skill
  `.claude/skills/atlas-design-system/` se actualiza para apuntar al sistema nuevo
  (hoy referencia Warm Editorial; si no se toca, futuras sesiones re-aplicarían el viejo).

### 4.2 Arquitectura de navegación
- **react-router v7 (modo librería)** con app shell: sidebar de navegación + header
  compacto; se conserva la paleta de comandos (⌘K) como navegación rápida.
- Rutas: `/pipeline` (default, kanban), `/jobs/:id` (detalle como página completa,
  reemplaza al DetailDrawer; tabs internos: resumen/CV/mensajes/entrevistas/research),
  `/analytics`, `/portfolio`, `/settings`, `/onboarding`. (Fases 2–4 añaden
  `/followups`, `/upskill` y secciones nuevas del detalle.)
- **TanStack Query** como capa de datos (reemplaza los `useState`/`load()` manuales de
  `App.tsx`): caching, invalidación declarativa y estados loading/error consistentes.
  `App.tsx` se descompone; la lógica de fetch vive en hooks por recurso (`src/hooks/`).
- El kanban (dnd-kit), NeedsAction, AnalyticsStrip, CommandPalette, FilterBar y
  SettingsModal migran de contenedor pero conservan su comportamiento.

### 4.3 Pasada de mejora UX sobre lo existente (en el rediseño)
- **Transparencia de score**: el detalle del job muestra el desglose de factores
  (reasons + knockouts que `score_job` ya produce) como lista legible — "por qué 74".
- Estados vacíos/cargando/error consistentes en todas las vistas (skeletons + mensajes
  accionables), toasts unificados.
- Responsive básico decente (la app hoy es desktop-only en la práctica; objetivo: usable
  en laptop pequeña, no mobile-first).

**Criterio de done F1:** paridad funcional verificada (flujos: buscar, mover en kanban,
detalle, aplicar, outcome, entrevistas, portfolio, export, settings), tests frontend
verdes + `vite build` + `./scripts/check.sh`, y QA visual con preview tools.

## 5. Fase 2 — Onboarding por perfil + geo-scoring + higiene de pipeline

**Objetivo:** cerrar el gap del punto 2 del usuario y subir la calidad del inventario de
jobs, todo determinista.

### 5.1 Onboarding wizard (web, por perfil)
Wizard multi-paso al crear/editar un perfil (reemplaza/absorbe `OnboardingGate.tsx`):
1. Identidad del perfil: nombre, dominio (seed-pack existente: `config/seeds/<domain>/`).
2. **País de residencia** (`candidate_country`) + regiones aceptables
   (`acceptable_regions`, p. ej. `[latam, worldwide]`) — alimentan el geo-scoring.
3. Tipo de trabajo: roles/aliases, seniority objetivo, `remote_required`,
   `onsite_locations`, años de experiencia (`candidate_years`).
4. Salario mínimo e idiomas.
5. **Importar CV**: upload PDF/DOCX → endpoint nuevo que reusa `engine/cv/import_cv.py`
   (draft YAML revisable, nunca escribe `master_cv.yaml` directo) → pantalla de revisión.
6. Empresas/fuentes iniciales (opcional; puede añadir por URL con resolve-ats, ver F3).

Backend: `GET/PUT /api/criteria` (lee/escribe el frontmatter de `criteria.md` del perfil
activo, validado con el modelo `Criteria`), `POST /api/cv/import` (multipart). Los datos
personales viven en `profiles/<id>/` y `config/` locales **gitignorados** (el repo es
público — regla existente que se mantiene).

### 5.2 Geo-scoring de remotos restringidos
- **Extracción** (determinista, `engine/normalize.py`): para jobs remotos, detectar
  restricción geográfica en `location` + `description` con patrones tipo
  `"(US|USA|UK|EU|…) only"`, `"must reside in …"`, `"based in …"`, `"eligible to work
  in …"`, `"remote (US)"`, listas de países en el campo location. Produce dos campos
  nuevos en `jobs` (migración vía el patrón `ADD COLUMN` de `engine/db/models.py`):
  - `geo_restriction` (texto crudo detectado, para mostrar en UI), y
  - `geo_scope` (normalizado: códigos de país/regiones, `worldwide` o `unknown`).
- **Criteria** (`engine/config.py`): `candidate_country: str = ""`,
  `acceptable_regions: list[str] = ["worldwide"]`, `geo_penalty: float = 12.0`.
- **Scoring** (`engine/scoring/fit.py`, nuevo factor 2c junto al gate onsite): si el job
  es remoto y `geo_scope` no cubre `candidate_country` ni intersecta
  `acceptable_regions` → `score -= geo_penalty` + knockout flag legible
  (`"remoto restringido a US"`). **Nunca descalifica** — siguen apareciendo, más abajo.
- Mapeo país→región embebido y pequeño (LatAm, EU, NA, APAC…), sin dependencias nuevas.
- UI: badge de restricción geo en la card del kanban y en el detalle.

### 5.3 Higiene de pipeline (importado de career-ops)
- **Liveness gate**: chequeo HTTP determinista por ATS (404/410, patrones "no longer
  available", redirect a careers genérico) antes de scorear; sweep batch sobre el
  inventario activo. Jobs muertos → estado `expired` (fuera del kanban, visibles en un
  filtro "expirados").
- **Detección de reposts/ghost jobs**: misma empresa + título fuzzy-igual con URL/id
  distinto ≥2 veces en 90 días → flag `repost` (badge en UI) + penalización leve en score.
- **Geo-mismatch**: contradicción entre `is_remote`/`workplace_type` y el body ("3 days
  in office") → knockout flag con la cita.
- **Ventana de re-aplicación**: en discovery, marcar (no ocultar) empresas con aplicación
  propia hace <N días (`re_apply_window_days` en criteria).
- **Archivo del posting**: al marcar Applied, snapshot del posting (texto + metadatos) se
  persiste, como evidencia para prep/negociación aunque el posting muera.

## 6. Fase 3 — Features de proceso deterministas

**Objetivo:** las features nuevas de mayor valor que no necesitan LLM.

### 6.1 Follow-ups de verdad (career-ops)
Sobre la tabla `followups` existente: cadencia por estado (Applied: 7d, máx 2 → cold;
Responded: 1d; Interview: thank-you 1d — defaults configurables en criteria),
**auto-seed del primer follow-up al marcar Applied**, y vista nueva `/followups` con
buckets URGENT / OVERDUE / waiting / COLD, drafts desde plantillas deterministas (reglas:
prohibido "just checking in", lead with value, <150 palabras) y registro de envío solo
con confirmación explícita del usuario.

### 6.2 Analytics + loop de aprendizaje (career-ops `analyze-patterns`)
Vista `/analytics` ampliada, calculada desde `events`/`application_outcomes`:
- Funnel real por transiciones de estado (descubierto→shortlist→aplicado→respuesta→
  entrevista→oferta) con tasas de conversión.
- **Score floor empírico**: distribución de score vs outcome ("ningún positivo bajo X").
- Conversión por fuente/ATS, por política remota, por role-term; tiempos de respuesta.
- **Cierre del loop**: panel de recomendaciones deterministas accionables con un click
  ("sube `shortlist_threshold` a 65", "bloquea la empresa X", "el término Y nunca
  convierte") que editan criteria/companies vía los endpoints de settings.

### 6.3 Story bank STAR+R (career-ops)
Tabla nueva `stories` (situación/tarea/acción/resultado/reflexión, tags de skill).
CRUD en la web (sección en `/settings` o en el detalle de entrevista). **Matcher
determinista** (port de `match-star.mjs`: scoring por overlap de tokens/skills) que ante
una pregunta o un JD rankea tus historias y las formatea (250–500 palabras) para pegar.
El brain (F4) puede poblar/refinar historias, pero el banco funciona sin LLM.

### 6.4 Knock-out pre-scan (career-ops)
Escaneo determinista del JD contra el perfil: visa/work authorization, años mínimos,
clearance, título/grado requerido, idioma. Chips de warning en card + detalle
("pide autorización de trabajo en US"). No penaliza el score (los knockouts ya existen);
es visibilidad pre-aplicación.

### 6.5 Discovery y operación
- **Reverse ATS discovery** (career-ops `scan-ats-full`): recorrer directorios públicos
  de empresas por ATS (Greenhouse/Lever/Ashby) filtrando por keywords del perfil →
  sugiere empresas nuevas para `companies.yaml` (con confirmación en UI).
- **Exponer en la web lo que hoy es CLI-only**: añadir empresa por URL
  (`resolve-ats`), importar `Connections.csv` de LinkedIn (upload), panel de salud
  (`doctor`/`status`: fuentes, DB, último run) en `/settings`.
- **Machine summary por job**: persistir el desglose completo del score (JSON) por
  corrida, de modo que analytics y el brain lo consuman determinísticamente.

## 7. Fase 4 — Features LLM vía brain + guided handoff

**Objetivo:** las features que requieren juicio LLM, ejecutadas por el brain y pedidas
desde la web sin aprender comandos.

### 7.1 Infraestructura de intents
- Tabla `intents`: `id, type, job_id?, payload JSON, status (pending|running|done|error),
  result_ref, created_at, completed_at`.
- Endpoints: `POST /api/intents` (encolar, origin-guarded), `GET /api/intents`
  (panel), resultados escritos por el brain en las tablas destino + `result_ref`.
- **Panel "Tareas del Brain"** (en el app shell, con badge de pendientes): lista intents,
  su estado y — clave — el bloque de instrucción copiable: *"Abre Claude Code en
  `~/dev/personal/atlas` y di: `corre atlas`"*. Una sola frase para todo; el brain drena
  la cola como paso 0 de su corrida (actualización de `brain/run_brain.py` + `SKILL.md`).
- Cada botón LLM en la web abre un mini-diálogo: qué hace, qué producirá, y que el
  resultado aparecerá aquí cuando corra el brain.

### 7.2 Features LLM importadas (los prompts son el producto)
- **Reviewer de CV/carta** (ai-job-search): loop drafter→reviewer con contexto fresco;
  el reviewer investiga la empresa y devuelve (a) edits estructurados JSON
  `{old, new, reason}` aplicables mecánicamente y (b) crítica en 4 categorías (keywords
  perdidos, ángulos empresa-específicos, reframing accionable, tono vs perfil). Reglas
  anti-fabricación de career-ops embebidas: "reformular, nunca inventar",
  tool-of-trade conflation ("usa X ≠ construyó X"), y el **backtrack test**: cada bullet
  reframed se clasifica OK/Flag/Never; los Flag se presentan en la web con acciones
  keep/soften/drop.
- **Legitimidad de postings** (career-ops Block G): evaluación ortogonal al score con
  tabla de señales ponderadas (edad, especificidad técnica, transparencia salarial…)
  → `legitimacy_tier` (alto/medio/bajo) + razones, badge en UI. Se encola en batch para
  el shortlist.
- **Upskill / gap analysis** (ai-job-search): dos pasadas (diff duro de skills +
  síntesis LLM), ponderación `(100 − fit_score)/100` (los trabajos donde peor encajas
  pesan más), heatmap Critical/High/Medium/Low, plan de estudio con recursos y orden por
  dependencias, y diff vs el reporte anterior. Vista nueva `/upskill` que renderiza el
  reporte persistido.
- **Interview prep profundo** (career-ops): audience map por ronda (recruiter/HM/peer/
  panel), question bank con fuentes citadas (regla: nunca inventar preguntas — las
  inferidas van etiquetadas), matching de historias del story bank, y **debrief**
  post-entrevista que actualiza el question bank y alimenta analytics. Extiende el
  `InterviewPanel` existente.
- **Expand de perfil** (ai-job-search): enriquecer el perfil desde GitHub/portfolio/
  syllabi oficiales de certs; aditivo, con fuente anotada y confirmación en la web.
- **Calidad de escritura transversal**: reglas voice/anti-slop de dos tiers (career-ops
  voice-dna) y "recruiter-side risk map + six-second gate" como paso previo de toda
  generación de CV/carta del brain.
- **Verificación visual de PDF** (ai-job-search): el brain compila el CV, lee el PDF
  renderizado y verifica layout (páginas exactas, títulos huérfanos) antes de dar por
  bueno el resultado.

## 8. Testing y verificación

- TDD por fase (skill superpowers): tests de motor primero (`uv run --group dev pytest`
  vía `rtk pytest`), componentes con Vitest.
- Casos obligatorios del geo-scoring: corpus de ejemplos reales ("Remote — US only",
  "Remote (must be UK-based)", "Remote LatAm", "Remote worldwide", remoto sin
  restricción, onsite) con esperados de extracción y de penalización.
- Gate por fase: `./scripts/check.sh` + `npm --prefix dashboard/frontend run build` +
  suite completa verde + QA con preview tools (verification-before-completion).
- Cierre de cada fase con `finishing-a-development-branch`; **merge local decidido por
  el usuario** (repo personal, master protegido con PR — se abre PR por fase).

## 9. No-objetivos y riesgos

**No-objetivos:**
- No API de Anthropic en el backend (se mantiene $0; el LLM es el brain).
- No auto-aplicación (human-in-the-loop duro, como career-ops).
- No nuevas fuentes con riesgo ToS (el acceso LinkedIn guest ya existe vía JobSpy; no se
  expande).
- No mobile-first (objetivo: desktop/laptop).
- No adoptar "files as canonical DB" de career-ops (SQLite ya es superior aquí).

**Riesgos y mitigaciones:**
- *F1 es grande y visual*: gate de mockups antes de tocar código; migración por vista
  con paridad verificada, no big-bang de CSS.
- *Extracción geo imprecisa*: penaliza solo con match confiable; `unknown` nunca
  penaliza; corpus de tests con ejemplos reales.
- *Guided handoff poco intuitivo*: una sola frase universal, visible en cada punto de
  contacto; el panel muestra el estado real de la cola.
- *Repo público*: onboarding y perfiles escriben solo en rutas gitignoradas; nada
  personal en commits (regla existente).
- *`App.tsx` monolito*: la descomposición en rutas/hooks es parte explícita de F1, con
  tests de componentes antes de mover lógica.
