# Atlas

**Tu centro de mando personal para la búsqueda de empleo**, corriendo 100% en tu máquina (macOS, o Windows vía WSL2).

Atlas descubre vacantes remotas, puntúa qué tan bien encajas, adapta tu CV a cada puesto
(optimizado para los filtros automáticos ATS), redacta los mensajes de contacto, detecta
referidos y te muestra —en un solo tablero— **qué está hecho**, **qué está pendiente** y
**exactamente qué enviar**. Cuesta **$0** más allá de tu suscripción a Claude Max que ya
pagas. **Nada se envía jamás sin tu aprobación.**

> El nombre clave "Atlas" es deliberadamente aburrido. Nada en pantalla delata que es una
> búsqueda de empleo.

---

## Índice

1. [Qué es esto en una frase](#1-qué-es-esto-en-una-frase)
2. [El problema que resuelve](#2-el-problema-que-resuelve)
3. [Las tres piezas de Claude que usa (y por qué)](#3-las-tres-piezas-de-claude-que-usa-y-por-qué)
4. [Cómo se mantiene en $0 — léelo primero](#4-cómo-se-mantiene-en-0--léelo-primero)
5. [El recorrido completo de una vacante, paso a paso](#5-el-recorrido-completo-de-una-vacante-paso-a-paso)
6. [Qué hace cada parte del código](#6-qué-hace-cada-parte-del-código)
7. [Cómo lo ejecutas tú](#7-cómo-lo-ejecutas-tú)
8. [Tus datos y tu privacidad](#8-tus-datos-y-tu-privacidad)
9. [Glosario](#9-glosario)

---

## 1. Qué es esto en una frase

Atlas es un robot de oficina que trabaja por ti **mientras duermes**: cada mañana sale a
buscar empleos que encajen contigo, te prepara el CV y los mensajes ya listos, y te deja un
tablero donde solo tienes que revisar y darle a "enviar". **Tú decides; él hace el trabajo
pesado.**

La regla de oro: **Atlas nunca aprieta el botón de enviar por ti.** Prepara todo hasta el
último centímetro y se detiene ahí. El envío siempre es tuyo.

---

## 2. El problema que resuelve

Buscar trabajo bien hecho es repetitivo y agotador:

- Hay que **revisar muchas fuentes** (LinkedIn, Indeed, bolsas de cada empresa…) todos los días.
- Hay que **descartar** lo que no encaja (presencial, junior, otro país, sueldo bajo).
- Hay que **reescribir el CV** para cada puesto, metiendo las palabras clave exactas que el
  filtro automático de la empresa busca, **sin inventar nada**.
- Hay que **escribir mensajes** a reclutadores, a quien contrata, y pedir referidos.
- Hay que **acordarse de hacer seguimiento** a los 3, 7 y 14 días.
- Y hay que **no perder el hilo** de en qué punto está cada postulación.

Atlas automatiza las partes mecánicas (buscar, filtrar, preparar borradores, recordar) y te
deja a ti solo las decisiones importantes (a cuál aplicar, qué enviar, cuándo).

---

## 3. Las tres piezas de Claude que usa (y por qué)

Atlas reparte el trabajo entre tres "manos" distintas, cada una con un papel claro:

| Pieza | Qué hace | Cuándo |
|---|---|---|
| **Claude Code** (esta sesión interactiva) | Construye y mantiene la maquinaria. Es quien programó todo Atlas. | Cuando tú y yo trabajamos juntos. |
| **Tarea programada de Cowork** (`atlas-job-brain`) | El "cerebro" diario. Corre solo, sin que estés. Busca, puntúa, prepara y redacta. **No envía nada.** | Cada día automáticamente (08:10). |
| **Claude en Chrome** | Las "manos supervisadas" en LinkedIn y formularios de empresa, usando **tu propia sesión**. Nunca envía solo. | Cuando tú lo pides, mirando. |

La idea: el cerebro automático prepara, tú y Claude-en-Chrome rematan el envío juntos.

---

## 4. Cómo se mantiene en $0 — léelo primero

Esta es la restricción que define todo el diseño. **El cerebro diario corre como una "tarea
programada de Claude Cowork / Desktop", que se descuenta de tu suscripción Max** —no de la
facturación por uso de la API.

Desde el **15 de junio de 2026**, `claude -p`, el Agent SDK y las GitHub Actions de Claude Code
pasaron a un **crédito medido aparte** (se cobra por token). Por eso Atlas **a propósito nunca
usa esos caminos**. Tres seguros convierten el "$0" en una garantía, no en una esperanza:

1. **El cerebro = una tarea programada de Cowork/Desktop** (ya creada como `atlas-job-brain`),
   nunca `claude -p` / Agent SDK / Routines en la nube.
2. **Desactiva los créditos de uso / facturación por excedente** en tu cuenta de Claude → así
   el sistema **falla cerrado**: si algo se pasara de la suscripción, el trabajo se detiene en
   vez de cobrarte.
3. **Sin `ANTHROPIC_API_KEY`** en tu terminal. El comando `uv run atlas doctor` lo verifica.

Todo lo demás —JobSpy, las APIs de ATS/Himalayas/Adzuna, SQLite, el tablero local, Claude en
Chrome— es gratis. La lista de verificación de una sola vez está en
[docs/SETUP.md](docs/SETUP.md). En Windows, Atlas corre dentro de WSL2 — ver la sección
"Windows" de [docs/SETUP.md](docs/SETUP.md).

---

## 5. El recorrido completo de una vacante, paso a paso

Esto es lo que pasa "por detrás" con cada empleo, desde que aparece en internet hasta que tú
lo envías. Cada vacante avanza por una **máquina de estados** (una fila de casillas); Atlas
guarda la fecha de cada salto para poder medir cuánto lleva en cada etapa.

```
descubierto → puntuado → preseleccionado → CV adaptado → mensajes redactados → LISTO
   → (tú envías) → aplicado → respondido → entrevista → oferta / rechazado → cerrado
```

**Paso 1 — Descubrir (`discover`).** Atlas sale a buscar a varias fuentes a la vez:
- **Bolsas de empleo de cada empresa (ATS)**, leídas directamente de su API pública y gratuita:
  Greenhouse, Lever, Ashby, SmartRecruiters. Es la fuente más limpia y estable.
- **Indeed** y **LinkedIn (modo invitado, sin login)** vía JobSpy — sin iniciar sesión, así que
  **no puede banear tu cuenta**; como mucho internet te limita la velocidad.
- **Himalayas** y **Adzuna**, APIs gratuitas enfocadas en remoto y con datos de salario.

Cada vacante recibe una **huella única** (un hash de empresa + puesto + ubicación). Si la
misma vacante aparece en dos fuentes, se reconoce y **no se duplica**. Si el cerebro se salta
un día y corre tarde, vuelve a procesar sin crear copias (esto se llama "idempotencia").

**Paso 2 — Puntuar el encaje (`score`).** Cada vacante se compara contra tus criterios
(`config/criteria.md`):
- **Reglas duras** (descartan): ¿es 100% remoto? ¿el puesto es de los tuyos —data analyst,
  data scientist, AI/ML engineer, "data specialist"—? ¿es senior?
- **Reglas suaves** (bajan o suben el puntaje): salario ≥ ~$70k, idioma EN/ES.
- **Banderas de descarte** ("knockout flags"): si pide ciudadanía, autorización de trabajo o
  clearance que no tienes, lo marca para que no pierdas tiempo.

Sale un puntaje de 0 a 100. Si pasa el umbral, la vacante queda **preseleccionada**.

**Paso 3 — Adaptar el CV (`tailor`).** A partir de tu CV maestro (`profile/master_cv.yaml`,
un archivo estructurado con toda tu experiencia real), Atlas genera una versión específica
para ese puesto. Dos controles:
- **Puerta de seguridad ATS (la dura):** el documento debe ser de una sola columna, con títulos
  estándar, fechas tipo "Mes-AAAA", sin tablas ni gráficos ni cajas de texto —porque eso es lo
  que rompe a los filtros automáticos. Después de generarlo, **vuelve a leer el texto del
  documento** para confirmar que se puede extraer bien.
- **Palabras clave:** inyecta el título exacto del puesto y los términos que la vacante pide
  (con su forma doble, p. ej. "Machine Learning (ML)"), **usando solo hechos reales tuyos —
  nunca inventa métricas ni experiencia**. Te entrega un **informe de cobertura** (qué palabras
  clave cubriste y cuáles te faltan), no un puntaje de vanidad.

Resultado: un **CV en DOCX y en PDF**, descargable desde el tablero, versionado por puesto.

**Paso 4 — Redactar los mensajes (`outreach`).** Atlas escribe, en tu voz, EN o ES:
- **Pedido de referido** (con salida fácil para la otra persona),
- **mensaje a reclutador** vs **mensaje a quien contrata** (enfoques distintos),
- **carta de presentación**,
- **email en frío** (75–100 palabras, llamada a la acción suave),
- **nota de LinkedIn** (corta, sin pitch).

Sigue una **escalera de prioridad**: referido → presentación cálida → InMail → email en frío
(el referido convierte 5–7× más, por eso va primero).

**Paso 5 — Detectar referidos (`referrals`).** Si importaste tu `Connections.csv` de LinkedIn
(tu propia exportación de datos), Atlas cruza tus contactos con la empresa de la vacante y, si
conoces a alguien ahí, **lo pone arriba del todo** para que pidas el referido en vez de aplicar
en frío.

**Paso 6 — Seguimientos (`followups`).** Atlas programa recordatorios de seguimiento a los días
0/3/7/14 y un cierre cordial. **Si la otra persona responde, los seguimientos se detienen solos.**

**Paso 7 — TÚ envías.** El tablero te muestra, por cada vacante lista: el enlace exacto para
postular, el CV, y todos los mensajes con botón de **Copiar**. Para formularios de empresa,
Claude en Chrome puede **pre-rellenar** (en tu sesión, mirando tú) y **tú** aprietas enviar.
Para email, se crean **borradores en Gmail** que tú revisas. **El cerebro nunca envía ni
postula por su cuenta.**

**Paso 8 — Seguir el rastro (tracking).** Todo queda en una base de datos local SQLite
(`data/atlas.db`): cada vacante, cada versión de CV, cada mensaje, cada contacto, cada
seguimiento, cada evento. De ahí salen las métricas del tablero (tasa de respuesta por canal y
por versión de CV, tasa de entrevista, cuánto lleva cada cosa en cada etapa).

---

## 6. Qué hace cada parte del código

```
atlas/
├── engine/                  ← El motor: Python puro, determinista, SIN IA. Rápido y predecible.
│   ├── discovery/           ← Paso 1: buscar vacantes
│   │   ├── ats/             ←   clientes de Greenhouse, Lever, Ashby, SmartRecruiters
│   │   ├── apis/            ←   Himalayas y Adzuna
│   │   ├── jobspy_source.py ←   Indeed + LinkedIn modo invitado
│   │   ├── registry.py      ←   detecta qué ATS usa una empresa siguiendo su URL de empleos
│   │   └── runner.py        ←   orquesta todas las fuentes y guarda en la BD (sin duplicar)
│   ├── scoring/             ← Paso 2: puntuar el encaje (fit.py = las reglas)
│   ├── cv/                  ← Paso 3: adaptar el CV
│   │   ├── tailor.py        ←   elige qué resaltar (sin inventar)
│   │   ├── keywords.py      ←   extrae palabras clave de la vacante
│   │   ├── render.py        ←   genera el DOCX y el PDF (PDF nativo con reportlab)
│   │   └── parse_check.py   ←   re-lee el documento para confirmar que el ATS lo entiende
│   ├── outreach/            ← Paso 4: redactar mensajes y programar seguimientos
│   ├── referrals/           ← Paso 5: importar y cruzar tus contactos de LinkedIn
│   ├── db/                  ← La base de datos: schema.sql (tablas) + models.py (acceso)
│   ├── heartbeat.py         ←   "latido": registra la última corrida con éxito (detecta caídas)
│   └── cli.py               ←   los comandos `atlas discover|score|tailor|brain|doctor|…`
│
├── brain/                   ← El cerebro diario
│   ├── run_brain.py         ←   el pipeline completo (descubrir→puntuar→preparar→redactar)
│   └── SKILL.md             ←   las instrucciones de la tarea programada de Cowork
│
├── advisor/                 ← Asesor de CV + LinkedIn (cómo mejorar tu perfil hacia tu rol objetivo)
│
├── dashboard/               ← El tablero web local
│   ├── backend/main.py      ←   API en FastAPI que lee la BD y la sirve como JSON en localhost
│   └── frontend/            ←   la interfaz (React + Vite + Tailwind, router multi-vista, diseño "Meridian"), en español, claro/oscuro
│       └── src/components/  ←   NeedsAction (qué hacer hoy), Board (kanban), AppShell (layout +
│                                rutas), AnalyticsStrip, CommandPalette (Cmd+K), BrainTasksPanel
│                                (Tareas del Brain); detalle de vacante en src/pages/JobDetailPage
│
├── config/                  ← Tu configuración
│   ├── criteria.md          ←   tus criterios de búsqueda (qué buscas, qué descartas)
│   ├── companies.yaml       ←   empresas objetivo y su ATS
│   ├── ontology.yaml        ←   diccionario de habilidades data/IA (canónico → alias/acrónimos)
│   └── sources.yaml         ←   qué fuentes activar
│
├── profile/master_cv.yaml   ← TU CV maestro estructurado (privado, no se sube a git)
├── data/atlas.db            ← La base de datos (privada, no se sube)
├── scripts/run.sh           ← Lanzador de un comando: construye el frontend y levanta el tablero
├── tests/test_engine.py     ← Pruebas del motor (no duplica, no inventa, ATS-seguro…)
└── docs/                    ← SETUP.md (instalación), ARCHITECTURE.md, SECURITY.md
```

**La distinción clave:** todo lo del `engine/` es **Python determinista, sin IA** — buscar,
filtrar, escribir en la BD, renderizar documentos, programar seguimientos. Es rápido, gratis
y predecible. La **IA (el cerebro Cowork)** solo se usa para lo que requiere criterio: ordenar
vacantes dudosas, elegir el contenido del CV, y redactar los mensajes en tu voz.

---

## 7. Cómo lo ejecutas tú

> ⚠️ **Nota sobre la terminal (zsh):** no copies comentarios con `#` dentro de un bloque de
> comandos. Tu shell **no** trata `#` como comentario al pegarlo, y rompe el comando. Copia
> solo la línea del comando.

**Levantar el tablero** (un solo comando):

```
cd /path/to/atlas
./scripts/run.sh
```

Construye el frontend la primera vez y abre la app en **http://127.0.0.1:8787**. Para
detenerla: `Ctrl+C`.

> **Git worktrees.** `profiles/` está gitignored (datos personales), así que un worktree
> nuevo arranca **sin** tus perfiles y verías el asistente de onboarding en vez de tus
> cuentas. `scripts/run.sh` lo detecta y apunta Atlas a los perfiles reales del checkout
> principal vía `$ATLAS_PROFILES_DIR` (una sola fuente de verdad, en vivo), así cada sesión
> ve las mismas cuentas y datos sin copiar nada. Para otros comandos (`uv run atlas …`) desde
> un worktree, exporta esa variable tú mismo:
> `export ATLAS_PROFILES_DIR="/ruta/al/checkout/principal/profiles"`.

**Refrescar vacantes manualmente** (o espera la corrida automática diaria de las 08:10):

```
uv run atlas brain
```

**Comandos útiles del motor:**

```
uv run atlas doctor                 verifica los seguros de $0 (sin API key, etc.)
uv run atlas discover               solo buscar vacantes
uv run atlas score                  solo puntuar el encaje
uv run atlas top                    ver las mejores vacantes en la terminal
uv run atlas tailor <job_id>        adaptar el CV a una vacante (DOCX + PDF)
uv run atlas prep <job_id>          preparar todo (CV + mensajes) de una vacante
uv run atlas import-connections <ruta-Connections.csv>   importar tus contactos de LinkedIn
uv run atlas referrals              ver referidos detectados
uv run atlas advise                 asesoría de CV/LinkedIn
uv run atlas status                 estado general (última corrida, salud de fuentes)
```

**Varias cuentas en la misma máquina (perfiles).** Atlas puede alojar varios perfiles
independientes —pensado para unas pocas personas de confianza (≤5)—, cada uno con su
**propia base de datos, su CV y sus criterios**, todo aislado y siempre local ($0). No hay
contraseñas: es un *selector* de perfil, no un control de acceso (la app solo escucha en
`127.0.0.1`).

- En el tablero, arriba a la derecha, un **selector** cambia de perfil al vuelo, sin
  reiniciar. La ★ marca el perfil dueño.
- La **corrida automática diaria (el cerebro) es solo del dueño** —corre sobre *tu*
  suscripción de Claude—. Los demás perfiles usan Atlas a mano (descubrir/preparar con un
  clic o por terminal), que es gratis. El brain se niega a correr para un perfil que no sea
  el dueño.

```
uv run atlas profiles list                                  ver perfiles, dominio y cuál está activo
uv run atlas profiles create <id> --label "Nombre" --domain <dominio>    crear un perfil nuevo
uv run atlas --profile <id> <comando>                       correr un comando para un perfil concreto
uv run atlas profiles init                                  (una sola vez) migrar tus datos al perfil "owner"
```

> La primera vez, `./scripts/run.sh` corre `atlas profiles init` solo: mueve tus datos
> actuales al perfil **owner** sin perder nada. Cada perfil nuevo edita su propio
> `profiles/<id>/config/criteria.md` y `profiles/<id>/profile/master_cv.yaml`.

> **Cualquier industria, no solo data.** Cada perfil tiene un **dominio** que elige su *seed pack*
> (`config/seeds/<dominio>/`): la ontología de skills, los criterios, el orden del CV, los bancos
> de entrevista y la voz del outreach se adaptan a esa industria. Vienen incluidos `data` (default)
> y `architecture`; cualquier otro cae al pack neutro `default` y se edita a mano. Ejemplo:
> `uv run atlas profiles create lucy --label "Lucy Paladines" --domain architecture`. Para añadir
> una industria nueva, copia `config/seeds/default/` a `config/seeds/<tu-dominio>/` y edítalo.

**Pruebas** (siempre vía RTK):

```
uv run rtk pytest
```

> Si las pruebas se quejan de paquetes faltantes (docx, rapidfuzz, pytest), corre
> `uv sync` antes: instala también el grupo `dev` (pytest, ruff) por defecto.

---

## 8. Tus datos y tu privacidad

Atlas corre **enteramente en tu máquina**. Nada de lo personal sale de tu equipo ni se sube a
GitHub. El `.gitignore` protege explícitamente: tu CV maestro (`master_cv.yaml`), la base de
datos (`*.db`), las carpetas `data/` y `profiles/` (donde vive cada perfil con su BD, su CV
y sus criterios), los documentos generados (`*.docx`, `*.pdf`), tu `Connections.csv` y
cualquier `.env`. Cada perfil queda **aislado** en su propia carpeta. El repositorio en
GitHub es **público**, así que la protección de tus datos es exactamente esa lista del
`.gitignore`: lo personal vive solo en tu máquina y **nunca** debe commitearse.

**Seguridad de dependencias:** la auditoría de **producción** da **0 vulnerabilidades**
(`npm --prefix dashboard/frontend run audit:prod`). Las alertas que pueda mostrar `npm audit`
son de herramientas de **construcción** (esbuild/Vite), no explotables en una app local que
solo escucha en `127.0.0.1`. El detalle completo está en [docs/SECURITY.md](docs/SECURITY.md).

---

## 9. Glosario

- **ATS** (Applicant Tracking System): el software con el que las empresas reciben y filtran
  CVs (Greenhouse, Lever, Ashby…). Si tu CV no está bien formateado, el ATS lo descarta antes
  de que un humano lo vea. Por eso el "Paso 3" es tan estricto con el formato.
- **Idempotente:** que puedes repetir la operación sin causar daño. La corrida del cerebro es
  idempotente: si corre dos veces, no duplica vacantes ni rehace trabajo ya hecho.
- **Máquina de estados:** la fila de casillas por la que avanza cada vacante (descubierto →
  puntuado → … → cerrado). Cada salto se marca con su fecha.
- **Knockout flag (bandera de descarte):** un requisito que te elimina automáticamente
  (ciudadanía, clearance), marcado para que no pierdas tiempo.
- **Heartbeat (latido):** un registro de la última corrida exitosa, para saber si el cerebro
  se cayó algún día y avisarte con un banner de "estuve caído N días".
- **JobSpy:** la librería que lee Indeed y LinkedIn en modo invitado (sin login).
- **Modo invitado:** leer vacantes públicas sin iniciar sesión → no puede banear tu cuenta.

---

*Hecho con Claude Code. El cerebro corre en tu suscripción Claude Max. Nada se envía sin tu
aprobación.*
