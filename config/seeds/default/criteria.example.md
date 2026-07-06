---
# Neutral starter criteria for any industry. Replace the bracketed values with YOUR target
# roles and rules. The deterministic scorer reads this frontmatter; the prose below is read
# by the Cowork brain for nuance.
roles: []                 # e.g. ["<tu rol objetivo>", "<rol alterno>"]
role_aliases: []
seniority: [senior, lead]
remote_required: false    # set true if you only want fully-remote roles
locations_allowed: [worldwide]
languages: [en, es]
must_haves: []
deal_breakers: []
knockout_terms: []
exclude_exec: true        # drop director/VP/head/chief titles (over-qualified for an IC track)
stretch_terms: []         # titles that usually want many years (penalized when below stretch_min_years)
stretch_min_years: 8
repositioning_target: ""  # empty = the advisor won't push you toward any specific re-framing
core_keywords: []         # the few must-appear terms the CV audit checks for
shortlist_threshold: 60
candidate_years: 0
# ── Geo (F2): tu país, para la penalización de remotos restringidos ──
candidate_country: ""          # tu código ISO-2 (p. ej. "ec"); vacío = factor apagado
acceptable_regions: [worldwide] # regiones cuyos remotos restringidos sí te sirven (latam/eu/na/apac)
geo_penalty: 12                # puntos que resta un remoto restringido fuera de tu alcance
re_apply_window_days: 0        # marca empresas donde aplicaste hace <N días; 0 = apagado
---

# Mi búsqueda

Describe en prosa qué buscas: tu rol objetivo, tu nivel, qué descartas y dónde quieres trabajar.
Esta sección la lee el cerebro de Atlas para matizar el ranking de vacantes dudosas. Cuanto más
clara y veraz, mejores recomendaciones.
