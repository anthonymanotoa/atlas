---
# ── Machine-readable criteria (parsed by the deterministic fit scorer) ────────
# Architecture / AEC seed pack. This domain is portfolio-driven and firm-relational,
# NOT data/ATS-anchored. The scorer optimizes for role/portfolio FIT, not keyword stuffing.
roles:
  - architect
  - project architect
  - architectural designer
  - junior architect
  - bim modeler
  - bim coordinator
  - draftsperson
  - architectural visualizer
role_aliases:
  - arquitecto
  - arquitecta
  - drafter
  - draughtsperson
  - cad technician
  - cad drafter
  - revit modeler
  - revit technician
  - bim technician
  - archviz
  - archviz artist
  - 3d artist
  - 3d visualizer
  - design architect
  - intermediate architect
  - part 1 architectural assistant
  - architectural assistant
  - job captain
seniority:
  - senior
  - lead
remote_required: false          # architecture has on-site roles; do NOT auto-reject in-person
onsite_locations: []            # si lo llenas (p. ej. [ecuador, ", ec", loja, quito, guayaquil]),
                                # las ofertas PRESENCIALES fuera de esas ubicaciones se DESCARTAN,
                                # pero las REMOTAS quedan exentas (mundo entero). Útil para
                                # "presencial solo en mi país, remoto desde cualquier parte".
                                # Nota: las ofertas EC vienen como "Ciudad, Prov, EC" → incluye ", ec".
locations_allowed:              # informativo
  - ecuador
  - latin america
  - remote
  - worldwide
languages:
  - es
  - en
language_hard: false            # true = DESCARTAR ofertas en otro idioma (no solo bajarlas). Útil
                                # si NO hablas inglés: pon languages: [es] y language_hard: true
                                # para ver solo ofertas en español.
must_haves: []                  # entry-level friendly: do not hard-require any one skill
deal_breakers:                  # disambiguate BUILDING architect from IT/"architect" postings
  - software architect
  - solutions architect
  - enterprise architect
  - cloud architect
  - data architect
  - security architect
knockout_terms: []              # surface, never auto-reject (e.g. application-form filters)
exclude_exec: false             # keep principal/studio-lead roles in scope
stretch_terms: []               # senior-only signals to flag as a reach (none by default)
stretch_min_years: 8
repositioning_target: ""        # set if pivoting lanes (e.g. "BIM coordination" or "archviz")
core_keywords:
  - revit
  - autocad
  - bim
  - sketchup
  - construction documents
  - architectural design
shortlist_threshold: 60
candidate_years: 0              # 0 = recent graduate / entry-level by default
# ── Geo (F2): tu país, para la penalización de remotos restringidos ──
candidate_country: ""          # tu código ISO-2 (p. ej. "ec"); vacío = factor apagado
acceptable_regions: [worldwide] # regiones cuyos remotos restringidos sí te sirven (latam/eu/na/apac)
geo_penalty: 12                # puntos que resta un remoto restringido fuera de tu alcance
re_apply_window_days: 0        # marca empresas donde aplicaste hace <N días; 0 = apagado
---

# Mis criterios de búsqueda — Arquitectura (notas para el cerebro de Atlas)

> Plantilla de ejemplo — reemplaza el texto entre [corchetes] con tu propio contexto.
> El cerebro de Atlas usa estas notas además de los criterios estructurados de arriba.
> Es una plantilla compartible: mantén el texto neutral y veraz, sin datos personales.

Busco roles de **arquitectura de edificios** (no de software). Soy [perfil, p. ej. recién
graduado/a, portafolio en construcción] y me importa el **fit de rol + portafolio** por encima
del título exacto: una oferta de "Architectural Designer", "BIM Modeler" o "Draftsperson" puede
encajar tanto como una de "Architect".

**Lo que busco:**
- **Local en Ecuador + remoto en LatAm/internacional.** No exijo 100% remoto: hay roles de obra
  presenciales que valen. Trabajo desde [tu ciudad/región]; hablo [tus idiomas, p. ej. español
  nativo, inglés básico — con honestidad].
- **Entry-level / junior es bienvenido.** No requiero ningún software como obligatorio; los
  proyectos académicos/de taller cuentan como experiencia real.
- Roles: Architect, Architectural Designer, Junior Architect, BIM Modeler, BIM Coordinator,
  Draftsperson, Architectural Visualizer / Archviz.

**El portafolio es el filtro decisivo.** En arquitectura el CV acompaña a un portafolio (casi
obligatorio) y normalmente pesa más. Sin link a portafolio una aplicación está incompleta.
La contratación es relacional: la carta/outreach con investigación de la firma es un entregable
de primera clase, no un extra.

**Señales de buen fit (suben el score):** stack base nombrado (Revit/AutoCAD/SketchUp/Adobe),
al menos un render en tiempo real (Lumion/Enscape/Twinmotion/D5/V-Ray), documentación de obra
(construction documents), nichos distintivos (rehabilitación patrimonial, diseño residencial),
firmas pequeñas/estudios que contratan por PDF + portafolio.

**Señales de mal fit (bajan el score / descartan):** roles de IT que usan "architect" en otro
sentido — software/solutions/enterprise/cloud/data/security architect (en `deal_breakers` para
desambiguar). En portales generalistas (LinkedIn/Indeed) marca como baja confianza los matches
ambiguos de "architecture" para revisión humana.

**Nota de título (sensible a la región):** en **Ecuador el título universitario CONFIERE el
título "Arquitecto/a"** — puedes nombrarte así desde la graduación; lo que se declara con
precisión es el **estado de registro** (SENESCYT, registro municipal/GAD; CAE opcional, la
colegiación NO es obligatoria). Al aplicar al extranjero, "Architect" puede estar protegido
(EE.UU., Reino Unido) → usa una etiqueta funcional segura ("Designer", "Part 1 Architectural
Assistant") y no impliques una licencia que no tienes.
