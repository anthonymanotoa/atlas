# Atlas Audit Uplift — Diseño

**Fecha:** 2026-07-11 · **Estado:** aprobado para plan · **Alcance:** toda la aplicación

## 1. Contexto

Dos insumos motivan este diseño:

**(a) Auditoría end-to-end con el perfil real `owner` (2026-07-11).** Resultado: el código
está sano (514 tests verdes, 0 crashes en los 21 grupos de comandos, discover trae 299
vacantes nuevas de 9 fuentes sin errores), pero hay problemas de **datos y estado** que
hacen que hoy nada sea enviable:

1. `profiles/owner/profile/master_cv.yaml` sigue siendo la plantilla "Ada Lovelace". El CV
   real está en `master_cv.draft.yaml` (con `_source_text` extraído del PDF) pero nunca se
   mapeó ni promovió. Todo tailor/prep/advise/portfolio sale con identidad falsa.
2. El brain no completa una corrida hace ~115h (umbral STALE: 26h). Dos intents pending
   desde 2026-07-07 (`legitimacy_batch`, `upskill_report`). Nunca se generó
   `MORNING_BRIEF.md`.
3. Degradaciones silenciosas: Adzuna reporta "✓ ok" con 0 resultados siempre (credenciales
   ausentes); fuentes demo (Lever demo board, empresas seed) activas en el perfil real;
   5 postings casi idénticos de CVS Health en el top (el flaggeo de reposts existe pero la
   shortlist no colapsa variantes); `fit=100.0` junto a `match 20%` confunde sin leyenda.
4. Portfolio research es una lista estática (9 URLs sin `name` ni `why`) + prompt para LLM.
   No existe búsqueda viva ni refresco.

**(b) Investigación de repos líderes (last30days, 2026-07-11).** Los tres proyectos top del
momento — career-ops (60K⭐), MadsLorentzen/ai-job-search, ApplyPilot — validan la filosofía
de Atlas (filter-not-flood, anti-fabricación, local-first) y marcan los gaps:

- **Reviewer pass** (ai-job-search): segundo agente que critica CV/carta y verifica el PDF
  renderizado (pdftotext, reading order, contact block) antes de darlo por listo.
- **Contact discovery** (career-ops): hiring manager/recruiter por vacante + draft de
  mensaje ≤300 chars. **Deep company research** por vacante.
- **Liveness check** (career-ops): descartar postings expirados antes del pipeline.
- **Post-aplicación** (career-ops/ai-job-search): interview story bank, upskill gap
  analysis, outcome calibration — Atlas ya tiene los esqueletos (`interview`, `outcome`,
  intent `upskill_report`) pero desconectados o atascados.

Raw de la investigación: `~/Documents/Last30Days/open-source-ai-job-search-automation-tools-raw-v3.md`.

## 2. Objetivos

1. Que Atlas sea **enviable hoy**: identidad real en todos los artefactos, brain corriendo,
   pipeline sin ruido.
2. Cerrar los gaps de calidad/features vs los líderes, respetando las invariantes de Atlas.
3. Terminar con una **validación end-to-end real**: usar la aplicación en profundidad con el
   perfil del dueño hasta enviar aplicaciones reales.

**No-objetivos (descartados a propósito):**
- Auto-submit / spray-and-pray (contra la filosofía; la comunidad lo está penalizando).
- Fuente Workday en este ciclo (ya existe el spike `plans/018-workday-source-spike.md`;
  alto mantenimiento — queda en backlog).
- Login-based scraping de LinkedIn (riesgo de ban; invariante de Atlas).

**Invariantes que ningún cambio puede romper:**
- $0: nada de `claude -p` / Agent SDK / API key. La IA va SOLO vía brain (Cowork) e intents.
- Atlas nunca envía nada; el usuario siempre aprieta enviar.
- Nunca inventar hechos en CV/mensajes (locks anti-fabricación).
- Datos personales solo en `profiles/` (gitignored); el repo es público.

## 3. Diseño por fases

### F0 — Saneamiento de datos y estado (prerequisito de todo)

**F0.1 CV real end-to-end.**
- Nuevo guard determinista `engine/cv/placeholder.py`: detecta identidad plantilla
  (nombre "Ada Lovelace", dominios `example.com`, teléfonos/URLs seed) en `master_cv.yaml`.
- `atlas doctor` lo reporta en rojo; el dashboard muestra un banner persistente y prominente
  ("Tu CV master es la plantilla — nada de lo generado es enviable");
  `tailor`/`prep`/`portfolio generate` imprimen advertencia prominente. Nada bloquea la
  ejecución (útil para demos/perfiles nuevos): es señalización fuerte, no un gate duro.
- Nuevo comando `atlas cv promote`: valida el draft (campos obligatorios, sin placeholders,
  sin `_source_text` residual), hace backup del master actual y promueve draft→master.
- El **mapeo** del draft (texto extraído → YAML estructurado) es trabajo de criterio: se
  hace en la sesión de ejecución junto al usuario (Claude Code edita
  `master_cv.draft.yaml` con los datos reales, el usuario valida, `cv promote` cierra).

**F0.2 Brain destrabado y observable.**
- Diagnóstico operativo de por qué la tarea Cowork `atlas-job-brain` no corre/registra
  heartbeat (fuera del repo; tarea de la sesión de ejecución con el usuario).
- `atlas brain --dry-run`: pipeline completo sin escrituras (planifica, reporta qué haría).
- Intents atascados: `atlas intents list` marca edad; nuevo `atlas intents requeue <id>` y
  expiración visible (pending > 48h ⇒ estado `stale` en dashboard y `status`).
- Drenar los 2 intents atascados como parte de la ejecución.

**F0.3 Higiene del perfil real.**
- Fuentes demo etiquetadas `demo: true` en `config/sources.yaml`/`companies.yaml`; discover
  las excluye para perfiles no-demo (o al menos advierte). Limpieza concreta del perfil
  `owner` en ejecución.

### F1 — Confiabilidad del pipeline

**F1.1 Salud de fuentes honesta.** Distinguir estados: `ok` (datos), `ok-vacío` (0 resultados
N corridas seguidas ⇒ advertencia con hint, p. ej. "adzuna: ¿credenciales?"), `sin-configurar`
(credenciales ausentes detectables ⇒ ni siquiera se intenta, se reporta como no configurada),
`error`. Visible en `status` y dashboard.

**F1.2 Dedup de shortlist.** Colapsar variantes/reposts (el flag ya existe en discover) en un
job canónico en `top` y dashboard, con contador "×N variantes" y acceso a las variantes.

**F1.3 Legibilidad del scoring.** `top` y dashboard muestran `fit` (encaje con criterios) y
`CV match` (cobertura de keywords) con etiquetas claras y leyenda; ordenar por una prioridad
blended documentada en vez de fit a secas cuando el CV match sea muy bajo.

**F1.4 Liveness check.** Antes de que una vacante shortlisted llegue a `top`/prep, verificación
barata de que el posting sigue vivo (HTTP status / respuesta del ATS); expirados se marcan
`expired` y salen del tablero activo.

### F2 — Calidad de output (patrón drafter-reviewer)

**F2.1 Reviewer determinista.** Ampliar `parse_check` a un **reporte de revisión** por CV
generado (`review.md` en el package): texto extraíble, bloque de contacto legible, orden de
lectura, páginas, cobertura de keywords (ya existe), scan de placeholders, claims vs master
CV (todo hecho listado debe existir en el master — lock anti-fabricación verificable).

**F2.2 Reviewer con criterio (intent `cv_review`).** Intent opcional del brain: crítica de
voz, énfasis y encaje contra la vacante, con veredicto y sugerencias; el resultado se guarda
y se muestra en el job detail. Nunca bloquea el flujo manual.

### F3 — Features nuevas (inspiradas en los líderes)

**F3.1 Contact discovery (intent `contact_discovery`).** Por vacante shortlisted: búsqueda
web (sin login) de recruiter/hiring manager probable; guarda contactos candidatos + draft de
mensaje corto en el package y job detail. Nunca envía.

**F3.2 Company research (intent `company_research`).** Brief por empresa (estrategia, noticias
recientes, cultura de ingeniería, señales de hiring) almacenado y reutilizado por outreach y
por el job detail.

**F3.3 Portfolio research viva.**
- Enriquecer los seeds (`config/seeds/<domain>/portfolio_references.yaml`) con `name` y `why`
  por cada URL (los 9 de `data` en ejecución).
- Intent `portfolio_research`: búsqueda real de portfolios de referencia del dominio,
  refresca la tabla `peer_portfolios` (nombre, URL, por qué es bueno, fecha).
- `PortfolioViewer` muestra tarjetas ricas (curados + descubiertos) y fecha del último
  refresh; CLI `atlas portfolio research` para inspeccionar/encolar el intent.

**F3.4 Post-aplicación conectado.**
- `upskill_report`: destrabado (F0.2) y visible en dashboard.
- Outcome calibration: reporte determinista de tasas (respuesta/entrevista por canal y por
  versión de CV) alimentado por `outcome`, visible en Analytics.
- Interview story bank: `interview prep` consume el package (CV adaptado + company research)
  y el banco de historias acumulado.

### F4 — Validación end-to-end con el perfil real (cierre obligatorio)

Con el usuario presente, en este orden, todo con el perfil `owner`:

1. `atlas doctor` limpio (sin placeholder, $0 seguro) y `status` sano.
2. Corrida completa del brain (o pipeline manual equivalente) → `MORNING_BRIEF.md` real;
   cola de intents drenada.
3. Walkthrough del dashboard en el navegador: todas las vistas (NeedsAction, Board, detalle,
   Analytics, Portfolio, Brain Tasks, selector de perfiles), claro/oscuro.
4. Selección de 3–5 vacantes reales del top → `prep` de cada una → revisar CV (DOCX+PDF con
   `review.md` limpio) y los 5 tipos de mensaje con datos reales.
5. `portfolio generate` real + portfolio research fresco.
6. `interview prep` de al menos una vacante.
7. **Aplicar de verdad a ≥3 vacantes** (el usuario envía; Claude en Chrome puede pre-rellenar
   formularios con el usuario mirando). Registrar con `outcome`/tracking y verificar que los
   followups quedan programados.
8. Criterio de éxito: ≥3 aplicaciones reales enviadas con materiales sin placeholders, brain
   con heartbeat fresco, y ninguna regresión (suite completa verde).

## 4. Arquitectura y ubicación

Regla de siempre: **determinista → `engine/`; criterio → intent del brain** (patrón $0 de la
cola existente, `plans/028` documenta la higiene del registry). Frontend sigue el design
system v2 (skill `atlas-design-system`). Cada feature nueva: schema en `engine/db/schema.sql`
+ models, comando/endpoint fino, y UI que lee de la API. TDD en todo (suite actual: 514).

Para preguntas de arquitectura durante la ejecución: `graphify query` en el checkout
principal (grafo fresco por hooks).

## 5. Riesgos

- **Brain/Cowork es entorno externo**: si la tarea programada está rota del lado de Cowork,
  el fix es operativo (recrearla), no de código. El plan lo trata como tarea con el usuario.
- **Calidad de contact discovery sin login**: puede devolver contactos débiles; se presenta
  como "candidatos" con confianza explícita, nunca como verdad.
- **Rate limits** en liveness/research: batch pequeño, caché y backoff (existe
  `docs/RATE_LIMITING.md`).
- **Repo público**: ningún dato personal en fixtures/tests; los enriquecimientos de seeds son
  genéricos del dominio, no del usuario.

## 6. Backlog explícito (fuera de este ciclo)

- Workday como fuente (retomar `plans/018`).
- Negotiation scripts (career-ops) — valioso pero post-oferta; esperar a tener entrevistas.
- Threads/summary de followups multi-canal.
