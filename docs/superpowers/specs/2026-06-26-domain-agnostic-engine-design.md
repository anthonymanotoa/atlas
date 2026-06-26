# Atlas — Motor agnóstico de dominio (design spec)

- **Fecha:** 2026-06-26
- **Estado:** propuesto (pendiente de revisión del usuario)
- **Alcance aprobado:** A+B completos (Atlas 100% agnóstico de industria; primer dominio nuevo: arquitectura)
- **Entradas de diseño:** [atlas-domain-coupling-ledger.md](../../research/atlas-domain-coupling-ledger.md),
  [architecture-cv-recommendations.md](../../research/architecture-cv-recommendations.md)

## 1. Contexto y objetivo

Atlas hoy funciona, pero su contenido está cableado a la persona "data scientist pivotando a IA/ML".
El **motor determinista** (`engine/cv/fit.py`, `keywords.py`, `match.py`, `tailor.py`) **ya es
config-driven y agnóstico** — lee todo de los archivos por-perfil. El problema es triple:

1. No existe un concepto **`domain`** en el perfil (el registry guarda solo `{id, label, is_owner}`).
2. Los **seeds** de un perfil nuevo copian los archivos **vivos de data science** (`ontology.yaml`,
   `sources.yaml`), no plantillas neutras → un perfil no-data arranca con skills/búsquedas de data y su
   `match_score` sale *silenciosamente mal*.
3. Varios **generadores** (advisor, outreach, portfolio, interview) y la **UI** hardcodean strings de la
   persona data/IA.

**Objetivo:** que *cualquier* industria funcione correctamente con solo elegir/editar config, sin tocar
código. Primer caso real: **Lucy Paladines**, arquitecta graduada 2026 (Loja, Ecuador).

**Criterio de éxito:**
- Un perfil `architecture` puntúa, matchea, adapta el CV, aconseja y redacta outreach **correctamente**
  contra ofertas de arquitectura (ontología AEC, sin "te falta IA", título "Arquitecta" no-data).
- El perfil `data`/owner produce **exactamente el mismo output que hoy** (retro-compatibilidad probada).
- Ningún string de "data/IA/ML" queda hardcodeado en un camino que vea un perfil no-data.

## 2. No-objetivos

- No reescribir el motor de scoring/matching (ya es agnóstico).
- No tocar el modelo de aislamiento de perfiles (`profiles/<id>/...`) ni el binding a `127.0.0.1`.
- No construir un portafolio de arquitectura real para Lucy (eso es trabajo de contenido aparte; la app
  *recuerda* y *enlaza* el portafolio, no lo genera).
- No añadir scrapers nuevos de boards de arquitectura en esta pasada (se documenta como follow-up; el pack
  de arquitectura ajusta `sources.yaml`/`search_terms` con lo existente).

## 3. Principio de arquitectura — 3 mecanismos anidados

```
(1) campo `domain` en el perfil
        ↓ selecciona
(2) seed-pack por dominio  →  puebla los archivos YA-correctos por-perfil
        ↓ los generadores/UI
(3) LEEN esa config por-perfil  (en vez de literales hardcodeados)
```

**Fuente de verdad en runtime = los archivos de config del PERFIL** (`profiles/<id>/config/*`,
`profiles/<id>/profile/master_cv.yaml`). El `domain` es (a) el selector de seed, (b) una etiqueta
mostrable, y (c) un *fallback* cuando un campo no está. Esto mantiene todo editable a mano y por-perfil.

## 4. Diseño detallado

### 4.1 El concepto `domain` (`engine/profiles.py`, `engine/cli.py`)

- `create_profile(profile_id, label=None, domain="data")` → persiste `domain` en la entrada del registry:
  `{id, label, domain[, is_owner]}`.
- `profiles.domain_of(profile_id) -> str` (default `"data"` si falta — retro-compat con perfiles viejos).
- `init_owner()` etiqueta al owner con `domain="data"`.
- CLI: `atlas profiles create <id> --label <l> --domain <d>` (default `data`); validar `domain` contra los
  packs disponibles en `config/seeds/` (error claro si no existe, listando los disponibles).
- `atlas profiles list` muestra el dominio junto al label.

### 4.2 Seed-packs por dominio (`config/seeds/<domain>/`, `engine/profiles.py:_SEEDS`)

- Reestructurar `_SEEDS` (hoy lista global) a `_seeds_for(domain)`:
  - Busca en `config/seeds/<domain>/` y cae a `config/seeds/default/` por archivo faltante.
  - **Deja de sembrar `ontology.yaml`/`sources.yaml` desde los archivos vivos.** Todos los seeds salen de
    `config/seeds/`.
- Archivos de un pack (todos opcionales salvo los 4 base):
  - `criteria.md`, `ontology.yaml`, `sources.yaml`, `companies.yaml`, `master_cv.example.yaml` (base)
  - `cv_layout.yaml` (orden/etiquetas de secciones + tipo de proof-source) — ver 4.6
  - `interview_topics.yaml` (bancos de preguntas) — ver 4.7
- Packs a crear en esta pasada: **`data`** (migra el contenido actual, output idéntico), **`architecture`**
  (nuevo, de la investigación), **`default`** (neutro, placeholders entre corchetes, ontología vacía).
- **Migración del repo actual:** los `config/*.example.*` y los `config/ontology.yaml`/`sources.yaml` vivos
  de hoy se mueven/copian a `config/seeds/data/`. Los archivos `config/*.yaml` vivos siguen existiendo para
  el checkout legacy (perfil pre-migración) pero ya no son la fuente de seed.

### 4.3 Des-acoplar scoring (`engine/scoring/fit.py`, `engine/config.py`, modelo `Criteria`)

Nuevos campos en `Criteria` (con defaults cross-domain seguros; el pack los setea por dominio):
- `exclude_exec: bool` — el **default global se mantiene `True`** (no rompe `data`); los packs lo setean
  explícitamente: `data=True`, `architecture=False`, `default=False`. Su *reason string* se templatiza
  ("título de dirección — fuera del track objetivo") en vez de "IC track". Así un arquitecto puede apuntar a
  "Director of Design" sin DQ silencioso.
- `stretch_terms: list[str]` y `stretch_min_years: int` — la penalización a "staff/principal/fellow" deja de
  ser constante; el pack `data` la conserva, `architecture` la vacía (ahí "Principal Architect" es normal).
- `senior_terms` / `exec_terms` / `junior_terms` — movidas de constantes de módulo al modelo, con defaults
  cross-domain (vocabulario white-collar genérico). Actualizar los comentarios "pivoting into AI".
- `core_keywords: list[str]` y `repositioning_target: str` (vacío = sin reposición) — ver 4.4.
- Tuning: `top_jd_keywords`, `max_skills`, `max_highlights_per_role` (hoy constantes en `match.py`/`tailor.py`)
  pasan a `Criteria` con los valores actuales como default.

El **logic** de scoring no cambia; solo de dónde lee sus listas/umbrales.

### 4.4 Des-sesgar generadores (`engine/advisor.py`, `engine/outreach/templates.py`, `engine/portfolio/*`)

- **Advisor:** borrar `AI_TERMS` (`:18-29`) y la lista inline `core` (`:161-182`). Las "skills núcleo/
  objetivo" se leen de la ontología del perfil + `criteria.core_keywords`. Los hallazgos "El resumen no
  menciona IA/LLM/ML" / "Reposiciona hacia IA/ML" (`:106-135`) se **gatean** tras `criteria.repositioning_target`
  (si está vacío → no se emiten). El `atlas advise` footer (`cli.py:382-392`) se neutraliza.
- **Outreach:** `templates.py` interpola un bloque **`basics.pitch`** del `master_cv.yaml`
  (`{identity_line, impact_domain, role_noun, value_verb}`) en vez de "senior data scientist… e-commerce".
  El `_skills_phrase` fallback (`:67-73`) deja de ser "data science and analytics" → neutro/derivado.
  `_ACRONYMS` (`:36-66`) se deriva de la ontología del perfil.
- **Portfolio:** generalizar la sección "GitHub" (`builder.py`) a un **proof-source pluggable** según
  `cv_layout.yaml`/config: `github` (repos), `visual_gallery` (Behance/Issuu/imágenes), o `none`. La query de
  `peer_research.py:43-49` (`site:github.io OR site:vercel.app`) se parametriza por dominio
  (arquitectura → `site:behance.net OR site:issuu.com OR site:cargo.site`). `peer_examples.py` se mueve a data
  por-dominio. El prompt `portfolio/prompt.py:33,47-116` toma label/temas/buckets/outcomes de `criteria` +
  `master_cv.basics.label`/`pitch`, y reemplaza el framing GitHub/Vercel/"AI builds".

### 4.5 Frontend neutro (`dashboard/frontend/src/**`, backend API)

- Exponer `domain` + label objetivo del perfil activo vía API (`/api/onboarding` o `/api/profiles`).
- Reemplazar strings "reposicionar hacia IA/ML" por el label del dominio / fallback neutro en
  `OnboardingGate.tsx:13-19,109-122`, `HelpGuide.tsx:36`, `CvAuditDialog.tsx:121-126`, `PortfolioViewer.tsx:110-114`.
- `App.tsx:52,138,388` + `HelpGuide.tsx:44`: renderizar `source_health` (que el backend ya expone) en vez de
  la lista `SEARCH_SOURCES` hardcodeada.
- `InterviewPanel.tsx:12`: `ROUNDS` (incluye `system_design`) → enum provisto por backend, traducido.
- Neutralizar tooltips: `Board.tsx:112`, `DetailDrawer.tsx:639` (ejemplos knockout), `HelpGuide.tsx:60`,
  `InterviewPanel.tsx:83-86` ("técnicas" → "específicas del rol").
- **Aplicar la skill `atlas-design-system`** (Warm Editorial) a cualquier copy/markup tocado.

### 4.6 Estructura de CV por-dominio (`engine/cv/render.py`, `parse_check.py`, `import_cv.py`, `build.py`)

- Nuevo `cv_layout.yaml` por-perfil (seedeado del pack): orden y etiquetas de secciones, qué secciones
  existen, y `proof_source` type. Para `architecture`: **Proyectos arriba** (orden junior), sección
  **Licenciatura/Registro** (SENESCYT/colegio), idiomas visibles.
- `render.py:16-33` lee el orden/labels de ahí (default = layout actual de data).
- `parse_check.py:41-44`: el check de secciones requeridas se driva del mismo layout, no de un trío fijo.
- `master_cv.example.yaml` por-dominio: scaffold con `basics.pitch`, `licensure`, y metadata de proyecto
  (tipología, escala, rol) para arquitectura.
- `build.py:16` `ALLOWED_LANGUAGES`: derivar de `criteria.languages` ∩ templates de render disponibles
  (no rechazar mercados no-en/es).

### 4.7 Bancos de entrevista (`engine/interview/interview_prep.py`)

- Mover `_BEHAVIORAL`, `_ROLE_TOPICS`, `_DEFAULT_TECH` (`:17-84`) a `interview_topics.yaml` por-perfil
  (seedeado del pack, en/es). `_DEFAULT_TECH` deriva de la ontología del perfil. `_star_evidence`/
  `_topics_to_review` ya derivan de CV+match (modelo a seguir).

### 4.8 Discovery y misc (`engine/discovery/jobspy_source.py`, `config/companies.*`)

- `jobspy_source.py:100`: quitar el fallback hardcodeado `'USA'`; que `criteria.remote_required`/`locations`
  manejen `is_remote`/país.
- `companies.yaml` del pack: vacío o específico del dominio (no firmas tech para arquitectura).

### 4.9 El pack de arquitectura (contenido, de la investigación)

- `ontology.yaml` AEC: Revit, AutoCAD, ArchiCAD, SketchUp, Rhino/Grasshopper, Dynamo, Lumion, Enscape,
  Twinmotion, D5 Render, V-Ray, Navisworks, BIM/ISO 19650, LEED, Adobe (PS/AI/InDesign), dibujo técnico,
  documentación de obra, fases de proyecto, rehabilitación patrimonial, diseño residencial… con alias/acrónimos.
- `criteria.md`: roles (architect, project architect, architectural designer, BIM modeler, draftsperson,
  archviz/3d artist), must_haves (revit/autocad), `exclude_exec=false`, `stretch_terms=[]`,
  `repositioning_target` vacío, idiomas (es nativo, en básico), localización (Loja/Ecuador + remoto),
  desambiguar **building-architect vs software-architect**.
- `sources.yaml`: search terms de arquitectura; on-site/local permitido (no `is_remote=true` forzado).
- `cv_layout.yaml`: proyectos arriba, sección Registro, `proof_source: visual_gallery`.
- `interview_topics.yaml`: portafolio, fases de proyecto, software/BIM, normativa, conducta.
- `master_cv.example.yaml`: scaffold de arquitecto con `basics.pitch`, `licensure`, metadata de proyecto.

## 5. Retro-compatibilidad y migración

- Perfiles existentes sin `domain` → tratados como `"data"` (default de `domain_of`).
- El owner (data) debe producir **output idéntico**: el pack `data` se crea moviendo el contenido actual;
  un test compara salidas clave antes/después.
- Los archivos `config/*.yaml` vivos del checkout legacy se conservan para el modo pre-migración.
- `EnterWorktree`/aislamiento: el **código** se edita en este worktree; los **datos de Lucy** viven en el
  checkout principal (`/Users/anthonymanotoa/dev/personal/atlas/profiles/lucy`).

## 6. Estrategia de pruebas (TDD)

Cada unidad se construye test-first. Suite vía `uv run rtk pytest` (117 verdes hoy — no deben romperse).
- **Retro-compat (data):** dado el perfil owner/data, `score`/`match`/`tailor`/`advise`/`outreach` producen
  las mismas salidas que el baseline actual (golden test).
- **`domain` concept:** `create_profile(..., domain='architecture')` persiste y `domain_of` lo devuelve;
  default `data` para entradas sin campo.
- **Seed-packs:** un perfil `architecture` recién creado tiene ontología AEC (no Python/SQL) y search terms
  de arquitectura; un perfil `data` mantiene los de hoy; `default` cae a placeholders neutros.
- **Scoring:** una oferta "Principal Architect" para un perfil `architecture` no recibe la penalización
  stretch; "Director of Design" no es DQ por `exclude_exec`. El perfil `data` sí mantiene ambos.
- **Advisor:** un CV de arquitecto sin "IA" NO genera el hallazgo "te falta IA"; con `repositioning_target`
  vacío no se emite ninguna sugerencia de reposición.
- **Matching/keywords:** una JD de arquitecto contra la ontología AEC da `match_score > 0` y skills faltantes
  significativas.
- **CV layout:** un perfil `architecture` renderiza Proyectos antes que Experiencia y una sección Registro;
  `data` mantiene su orden.
- **Outreach:** el cuerpo usa `basics.pitch`, sin "senior data scientist".
- **Frontend:** (donde haya tests) el onboarding no muestra strings IA/ML para `architecture`.

## 7. Inventario de archivos (resumen)

**Backend:** `engine/profiles.py`, `engine/cli.py`, `engine/config.py` (modelo Criteria), `engine/scoring/fit.py`,
`engine/advisor.py`, `engine/outreach/templates.py`, `engine/portfolio/{builder,prompt,peer_research,peer_examples}.py`,
`engine/cv/{render,parse_check,import_cv,build,match,tailor}.py`, `engine/interview/interview_prep.py`,
`engine/discovery/jobspy_source.py`, rutas API del dashboard backend.
**Contenido nuevo:** `config/seeds/{data,architecture,default}/...`.
**Frontend:** `OnboardingGate.tsx`, `HelpGuide.tsx`, `CvAuditDialog.tsx`, `PortfolioViewer.tsx`, `App.tsx`,
`InterviewPanel.tsx`, `Board.tsx`, `DetailDrawer.tsx`.
**Docs:** `README.md` (describir el advisor genéricamente; IA/ML como *ejemplo* de track).

## 8. Preguntas abiertas / riesgos

- El refactor del advisor toca `audit_cv` compartido → cubrir con tests antes de mover lógica.
- `prompt`/`peer_examples` de portfolio son material que lee el brain LLM; el cambio es de contenido, bajo riesgo.
- Boards de arquitectura (Archinect/Dezeen/RIBA) NO se integran como scrapers aquí (follow-up); el pack solo
  ajusta search terms sobre las fuentes existentes (JobSpy/ATS/Himalayas/Adzuna).
- Desambiguación building-architect vs software-architect en boards generalistas: heurística por keywords en
  `criteria` + marcar baja confianza; no perfecta.
