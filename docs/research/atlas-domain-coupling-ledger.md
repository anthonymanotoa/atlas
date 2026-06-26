# Atlas — Ledger de acoplamiento al dominio "data"

> Entrada de diseño para volver Atlas agnóstico de industria (primer caso: arquitectura/Lucy).
> Generado por un barrido paralelo de 8 lectores sobre todos los subsistemas + síntesis.

## Diagnóstico en una frase

El **motor determinista** (`engine/cv/fit.py`, `keywords.py`, `match.py`, `tailor.py`) **ya es
agnóstico y config-driven** — lee todo de los archivos por-perfil. El problema está en (a) que **no
existe un concepto `domain` en el perfil**, (b) que **los seeds copian los archivos vivos de data
science** en vez de plantillas neutras, y (c) que varios **generadores y la UI hardcodean strings**
de la persona "data scientist pivotando a IA/ML".

**Leyenda:** **[BLOQUEA]** = produce output incorrecto/engañoso para un perfil no-data ·
**[COSMÉTICO]** = sesga o mal-etiqueta pero no corrompe resultados.

## Temas

### T1 — Listas de skills/keywords hardcodeadas
- **[BLOQUEA]** `config/ontology.yaml` — gazetteer 100% DS/AI; para una oferta de arquitecto (Revit,
  AutoCAD, BIM) `extract_jd_keywords()` da ~0 → `match_score ≈ 0` y "skills faltantes" vacío.
- **[BLOQUEA]** `engine/advisor.py:18-29` (`AI_TERMS`) y `:161-182` (lista `core` de data); marca como
  deficiente cualquier CV sin IA.
- **[BLOQUEA]** `engine/outreach/templates.py:36-66` (`_ACRONYMS` DS/AI).
- **[COSMÉTICO]** `engine/cv/build.py:16` `ALLOWED_LANGUAGES={'en','es'}` (gate duro, no data-specific).
- **Mecanismo:** ontología por-perfil seleccionada por `domain`; los duplicados leen de ahí.

### T2 — Prompts LLM con supuestos de dominio
- **[BLOQUEA]** `engine/portfolio/prompt.py:33,47-116` — persona "Senior Data Scientist & AI Engineer",
  buckets de skills DS, temas (retención/experimentación/GenAI), stack Next.js+Vercel, sección "AI builds".
- **[BLOQUEA]** `advisor/cv_linkedin_advisor.md` — instruye reposicionar "hacia AI/ML".
- **Mecanismo:** templatear los sustantivos de dominio desde `criteria.md` + `master_cv.basics.label`.

### T3 — Seeds y defaults de onboarding (la pieza maestra)
- **[BLOQUEA]** `engine/profiles.py:29-35` (`_SEEDS`) — **`ontology.yaml` y `sources.yaml` se siembran de
  los archivos VIVOS de DS** → un perfil nuevo arranca con skills/búsquedas de data (match silenciosamente mal).
- **[BLOQUEA]** `engine/profiles.py:171-182` + `engine/cli.py:506-524` — `create_profile(id, label)` no captura
  ni guarda `domain`; registry = `{id, label, is_owner}`.
- **[BLOQUEA]** `config/criteria.example.md` y `config/sources.yaml` — roles/términos DS por defecto.
- **Mecanismo (keystone):** (1) campo `domain` en `create_profile()` + `--domain` + `domain_of(id)`;
  (2) seed-packs por dominio `config/seeds/<domain>/...` con fallback `default`; (3) **dejar de sembrar
  ontology/sources de los archivos vivos**; (4) `domain='data'` por defecto (retro-compat).

### T4 — Copy de advisor/outreach/portfolio
- **[BLOQUEA]** `engine/advisor.py:40-42,106-135` — "El resumen no menciona IA/LLM/ML", "Reposiciona hacia IA/ML".
- **[BLOQUEA]** `engine/outreach/templates.py:100-198` — cuerpos firman "senior data scientist… e-commerce".
- **[BLOQUEA]** `engine/portfolio/builder.py` — sección "GitHub" que busca repos como prueba de portafolio
  (arquitectos usan Behance/Issuu/planos, no repos); `peer_examples.py` 100% DS.
- **Mecanismo:** bloque `basics.pitch` por-perfil + "external proof source" pluggable (repos vs galería visual);
  gatear los hallazgos "reposiciónate hacia X" tras `criteria.repositioning_target`.

### T5 — Copy/labels del frontend
- **[BLOQUEA]** `OnboardingGate.tsx:13-19,109-122`, `HelpGuide.tsx:36`, `CvAuditDialog.tsx:121-126`,
  `PortfolioViewer.tsx:110-114` — repiten "reposicionar hacia IA/ML" / persona DS.
- **[BLOQUEA]** `App.tsx:52` (`SEARCH_SOURCES` lista tech hardcodeada; el backend ya expone `source_health`).
- **Mecanismo:** exponer `domain`/label objetivo por la API y leer lo que el backend ya da; fallback neutro.

### T6 — Reglas/pesos de scoring
- **[BLOQUEA]** `engine/config.py:45` + `engine/scoring/fit.py:153-156` — `exclude_exec` default **True**:
  DQ silencioso de Director/Head/Chief (un arquitecto puede apuntar a "Director of Design").
- **[BLOQUEA]** `engine/scoring/fit.py:22-27,157-168` — penaliza títulos staff/principal/fellow asumiendo
  "IC overqualified"; en arquitectura "Principal Architect" es normal → empuja al candidato bajo la shortlist.
- **Mecanismo:** mover las listas de títulos al modelo `Criteria` (defaults cross-domain); gatear la
  penalización stretch y suavizar `exclude_exec`.

## Cambios — set (A) mínimo para que arquitectura funcione bien
1. Campo `domain` en perfiles (`profiles.py`, `cli.py`, registry, `domain_of`).
2. Seed-packs por dominio + dejar de sembrar ontology/sources de archivos vivos; autorar pack `architecture`.
3. Arreglar los 2 bloqueadores de scoring (gate stretch + `exclude_exec` neutro, seteados en el seed).
4. Des-sesgar el advisor (borrar `AI_TERMS`/`core`; leer de criteria/ontología; gatear "reposición").
5. Parametrizar identidad de outreach (`basics.pitch`).
6. Parametrizar los 2 prompts LLM (portfolio + cv_linkedin_advisor).
7. Que el frontend deje de decir "reposiciónate hacia IA/ML" (exponer `domain` por API + fallback neutro).

**Esfuerzo (A):** ~1,5-2,5 días de código + ~0,5-1 día curando el pack de arquitectura (ontología AEC).

## Cambios — set (B) full agnóstico (sobre A)
8. Externalizar bancos de preguntas de entrevista (`interview_prep.py`) a config por-perfil/dominio.
9. Generalizar proof-source de portafolio + galerías peer a data por-dominio.
10. Promover constantes de tuning (`TOP_JD_KEYWORDS`, `MAX_SKILLS`, listas de títulos) a `Criteria`.
11. Estructura de CV por-perfil (`render.py`/`parse_check.py`): secciones configurables + sección
    Licenciatura/Registro + scaffold por-dominio en `import_cv.py`/`master_cv.example.yaml`.
12. Derivar `ALLOWED_LANGUAGES` de `criteria.languages`.
13. Suavizar defaults de discovery (`jobspy_source.py:100` 'USA'; `companies.yaml` vacío/por-dominio).
14. Terminar el frontend (rounds de entrevista, `source_health`, tooltips neutros, README).
15. Packs starter `data` + `architecture` + `default` neutro, y documentar cómo añadir un dominio.

**Esfuerzo (B):** +4-7 días sobre A. El coste recurrente por dominio es **curación de contenido**.

## Nota de diseño
Tres mecanismos anidados cubren ~90%: **(1) campo `domain` en el perfil → (2) seed-packs por dominio que
pueblan los archivos ya-correctos por-perfil → (3) que los generadores/UI LEAN esa config en vez de literales.**
El motor casi no se toca; el coste real es curar contenido por dominio.
