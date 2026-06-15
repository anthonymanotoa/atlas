"""Build a detailed, personalized LLM prompt the user can paste into Claude/ChatGPT/Lovable to
have their portfolio built for them.

The user asked for the prompt to be (a) as detailed as possible and (b) to spell out exactly
what the portfolio will contain. So we compose it from their REAL master_cv.yaml (name, role,
summary, skills, experience, metrics) plus the cross-cutting patterns distilled from the best
peer portfolios. Atlas does NOT build the site — it hands the user a ready-to-paste brief.
"""

from __future__ import annotations


def _clean(s: str | None) -> str:
    return " ".join((s or "").split())


def _experience_block(cv: dict) -> str:
    lines: list[str] = []
    for e in cv.get("experience") or []:
        title = e.get("title", "")
        company = e.get("company", "")
        dates = f"{e.get('start', '')} – {e.get('end', '')}".strip(" –")
        lines.append(f"- {title} — {company} ({dates})")
        for hl in (e.get("highlights") or [])[:4]:
            lines.append(f"    • {_clean(hl)}")
    return "\n".join(lines)


def build_portfolio_prompt(cv: dict) -> str:
    """Return a long, copy-paste-ready prompt for an LLM to build the user's portfolio site."""
    b = cv.get("basics", {}) or {}
    name = b.get("name") or "[tu nombre]"
    label = b.get("label") or "Senior Data Scientist & AI Engineer"
    summary = _clean(b.get("summary"))
    skills = ", ".join(cv.get("skills") or [])
    links = " · ".join(v for v in [b.get("linkedin"), b.get("github"), b.get("email")] if v)
    education = "; ".join(
        " ".join(
            x
            for x in [ed.get("degree"), ed.get("area"), "—", ed.get("institution")]
            if x and x != "—"
        ).replace("  ", " ")
        for ed in (cv.get("education") or [])
    )
    experience = _experience_block(cv)

    return f"""\
Actúa como un ingeniero front-end senior + diseñador de producto. Vas a construir mi **sitio de
portafolio personal** (one-page, responsive, listo para producción). Es para conseguir un rol
**remoto** de Senior Data Scientist / AI Engineer / Analytics Engineer en empresas
internacionales, así que el copy del sitio va en **inglés** (con un toggle opcional ES).

═══════════════════════════════════════════════════════════════════════
MIS DATOS REALES (usa SOLO esto; nunca inventes métricas, empresas ni experiencia)
═══════════════════════════════════════════════════════════════════════
Nombre: {name}
Título objetivo (hero): {label}
Links: {links}
Posicionamiento (resumen): {summary}

Skills (agrúpalas tú por dominio: Analytics · Data/Analytics Engineering · GenAI/LLM · Viz/BI):
{skills}

Experiencia (usa los logros tal cual; puedes reescribir el wording pero NO el hecho):
{experience}

Educación / certificaciones: {education}

═══════════════════════════════════════════════════════════════════════
ESTRUCTURA EXACTA DEL PORTAFOLIO (en este orden)
═══════════════════════════════════════════════════════════════════════
1. HERO: mi nombre + el título objetivo EXACTO + una sola línea de posicionamiento centrada en
   el OUTCOME que genero (retención / AOV / CVR / LTV / experimentación / automatización con IA
   para e-commerce). Dos CTAs: "View projects" y "Get in touch". Botón de "Download CV".
2. STAT BAR (chips de credibilidad, solo números reales): p.ej. "5+ años", "0→40k usuarios",
   "~12 h/semana ahorradas con IA", "100% remoto", "EN/ES". Ajusta a mis datos reales.
3. ABOUT: 3–4 frases humanas y concretas — ecuatoriano basado en Anytown, 100% remoto,
   bilingüe, ex-cofundador de una fintech (a fintech startup), hoy en retención + experimentación + GenAI en
   e-commerce. Nombra empresas reales (Acme Corp, Globex) como prueba social. Incluye foto.
4. SKILLS por dominio (4 grupos), no una nube plana.
5. PROYECTOS (el centro) — agrúpalos por TEMA: "Retention & Lifecycle", "Experimentation /
   A-B Testing", "GenAI & Automation". Para cada proyecto usa SIEMPRE la misma tarjeta:
       título · categoría · año · resumen 1 línea · 3 bullets de detalle ·
       1 línea de IMPACTO cuantificado en negrita · chips de stack · links (repo/demo si existe).
   El resultado va PRIMERO, luego la técnica. 3–5 proyectos profundos > 15 superficiales.
6. WRITING / NOTES (opcional pero suma): 2–3 entradas — p.ej. un write-up de A/B testing o de
   automatización con LLMs. Diferencia mucho para roles remotos.
7. EXPERIENCE + EDUCATION (estilo CV, conciso).
8. CONTACT: email + LinkedIn + GitHub + botón de CV. Repite el CTA "Let's talk".

═══════════════════════════════════════════════════════════════════════
DISEÑO Y STACK
═══════════════════════════════════════════════════════════════════════
- Stack: Next.js (App Router) + Tailwind CSS + tipografía Geist. Componentes limpios.
- Minimal, contenido primero, mucho espacio en blanco, jerarquía tipográfica fuerte.
- Toggle claro/oscuro. Rápido, mobile-first, accesible (semántico, headings claros para ATS/IA).
- Sin librerías pesadas innecesarias. Animaciones sutiles (fade/slide), nada recargado.
- Entrega: estructura de archivos completa + instrucciones para correrlo y desplegarlo en Vercel.

═══════════════════════════════════════════════════════════════════════
LO QUE HACEN LOS MEJORES (inspírate en esto, no copies)
═══════════════════════════════════════════════════════════════════════
- Proyecto autocontenido en la página: el reclutador no debería tener que entrar a GitHub.
- Cuantifica todo (%, $, tiempo, usuarios). Resultado de negocio primero, técnica después.
- Una sección de "AI builds" separada para que mi pivote a IA/LLM se vea de un vistazo.
- "Last updated" por proyecto = portafolio vivo. Foto real + algo de personalidad en el About.
- Evita: proyectos flacos sin métricas, datasets de juguete, bios vagas, links rotos.

═══════════════════════════════════════════════════════════════════════
ENTREGABLE
═══════════════════════════════════════════════════════════════════════
Primero hazme 3–5 preguntas para llenar los huecos (qué proyectos reales destaco, métricas
exactas, si tengo demos en vivo, foto, dominio). Luego genera el sitio completo, listo para
`npm install && npm run dev`, y dime cómo desplegarlo en Vercel con mi dominio.
"""
