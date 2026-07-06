---
# ── Machine-readable criteria (parsed by the deterministic fit scorer) ────────
roles:
  - data scientist
  - data analyst
  - ai engineer
  - machine learning engineer
role_aliases:
  - data specialist          # e.g. an adjacent/alternate title you'd accept
  - analytics engineer
  - ml engineer
  - applied scientist
  - data science
  - business intelligence analyst
  - bi analyst
  - ai/ml engineer
  - genai engineer
seniority:
  - senior
  - sr
  - lead
  - staff
  - principal
  - ssr            # accept mid-senior too; tune down if too noisy
remote_required: true
locations_allowed:
  - worldwide
  - latam
  - united states
  - europe
languages:
  - en
  - es
salary_floor_usd: 70000
salary_hard: false           # most postings hide salary; treat as a soft down-rank
must_haves:
  - sql
  - python
deal_breakers:
  - on-site only
  - hybrid required
  - unpaid
  - internship
knockout_terms:               # surface (don't auto-reject) — usually application-form filters
  - security clearance
  - must be us citizen
  - us citizenship required
  - active clearance
shortlist_threshold: 62
# ── Quality gates (P1-A) — all optional, sane defaults if omitted ─────────────
max_age_days: 45              # 0 = off; postings older than this are down-ranked
freshness_hard: false         # true = a stale posting is disqualified, not just down-ranked
exclude_exec: true            # drop Director/VP/Head/Chief roles (over-qualified for an IC track)
max_years_required: 12        # 0 = off; flag postings demanding more years than this
company_blocklist: []         # never surface these companies (matched case/suffix-insensitively)
#  - acme
# ── Domain positioning (advisor) — empty = neutral; the data track is AI-forward ──
repositioning_target: "AI/ML"   # advisor nudges the CV toward this (truthfully); "" disables it
core_keywords:                  # must-appear terms the CV audit checks for this domain
  - python
  - sql
  - machine learning
  - large language models
  - a/b testing
  - statistics
  - generative ai
# ── Geo (F2): tu país, para la penalización de remotos restringidos ──
candidate_country: ""          # tu código ISO-2 (p. ej. "ec"); vacío = factor apagado
acceptable_regions: [worldwide] # regiones cuyos remotos restringidos sí te sirven (latam/eu/na/apac)
geo_penalty: 12                # puntos que resta un remoto restringido fuera de tu alcance
re_apply_window_days: 0        # marca empresas donde aplicaste hace <N días; 0 = apagado
---

# Mis criterios de búsqueda (notas para el cerebro de Atlas)

> Plantilla de ejemplo — reemplaza el texto entre [corchetes] con tu propio contexto.
> El cerebro de Atlas usa estas notas además de los criterios estructurados de arriba.

Soy [tu rol actual] en transición hacia **[tu objetivo, p. ej. AI/ML]**. Mi título actual
puede no coincidir con lo que busco, así que **no me fijo solo en el título** — me importa el
contenido: analítica, experimentación (A/B testing), modelado, y cada vez más
construir cosas con **IA/LLMs**.

**Lo que busco:**
- **100% remoto**, sin excepción. Trabajo desde [tu región]; hablo [tus idiomas].
- **Seniority medio-alto** (senior idealmente; acepto roles "mid-senior" fuertes).
- **Salario objetivo [tu piso, p. ej. ~$70k USD/año] en adelante.** La mayoría de ofertas no lo
  indican; cuando no aparezca, **no descartes** — solo prioriza las que sí cumplen.
- Roles: Data Scientist, Data Analyst, AI Engineer / ML Engineer, Analytics Engineer.

**Señales de buen fit (suben el score):** producto data-driven, experimentación,
SQL + Python, cloud (AWS/GCP), trabajo con LLMs / GenAI, equipos remotos maduros.

**Señales de mal fit (bajan el score / descartan):** presencial u híbrido obligatorio,
prácticas/internship, roles puramente de data engineering pesado (Spark/Scala sin
analítica), o que exijan ciudadanía/clearance de un país (márcalo, no lo descartes solo).
