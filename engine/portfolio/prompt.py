"""Build a detailed, personalized LLM prompt the user can paste into Claude/ChatGPT/Lovable to
have their portfolio built for them.

The user asked for the prompt to be (a) as detailed as possible and (b) to spell out exactly
what the portfolio will contain. So we compose it from their REAL master_cv.yaml (name, role,
summary, skills, experience, metrics) plus the cross-cutting patterns distilled from the best
peer portfolios. Atlas does NOT build the site — it hands the user a ready-to-paste brief.

The brief is DOMAIN-AGNOSTIC: the target role, skill grouping, project themes and the proof
framing are all derived from the candidate's profile (master_cv basics, criteria, cv_layout
proof_source) instead of a hardcoded data-scientist persona. A data candidate (proof_source
"github") gets a code/repo framing; an architecture candidate (proof_source "visual_gallery")
gets a visual project gallery + external links (portfolio/Behance/Issuu), no code repos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.config import Criteria


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


def _target_role(b: dict, criteria: Criteria | None) -> str:
    """Hero/title — the candidate's REAL target role, never a hardcoded persona.

    Priority: basics.label → criteria.roles (title-cased, joined) → a neutral fallback.
    """
    label = _clean(b.get("label"))
    if label:
        return label
    if criteria and criteria.roles:
        return " / ".join(r.strip().title() for r in criteria.roles[:3])
    return "[tu rol objetivo]"


def _domain_descriptor(criteria: Criteria | None) -> str:
    """A short, profile-derived domain hint so the LLM groups skills/projects sensibly,
    instead of us hardcoding data-specific buckets (Analytics/GenAI/Retention…)."""
    if criteria and criteria.roles:
        return ", ".join(r.strip() for r in criteria.roles[:4])
    return ""


def _links_block(b: dict) -> str:
    """Whatever the candidate actually provides — never assume github/email exist."""
    candidates = [
        b.get("linkedin"),
        b.get("website"),
        b.get("portfolio"),
        b.get("behance"),
        b.get("issuu"),
        b.get("github"),
        b.get("email"),
    ]
    return " · ".join(v for v in candidates if v)


def _education_block(cv: dict) -> str:
    return "; ".join(
        " ".join(
            x
            for x in [ed.get("degree"), ed.get("area"), "—", ed.get("institution")]
            if x and x != "—"
        ).replace("  ", " ")
        for ed in (cv.get("education") or [])
    )


def _proof_guidance(proof_source: str, b: dict) -> tuple[str, str, str]:
    """Return (projects_hint, proof_section, stack_section) framing, keyed by proof_source.

    - visual_gallery → foreground a VISUAL project gallery + external links (portfolio/Behance/
      Issuu/site); no code repos, no mandated web framework.
    - github         → code-first proof: link repos/demos, self-contained on the page.
    - none           → no dedicated proof section, no stack mandate.
    """
    if proof_source == "visual_gallery":
        ext = _links_block(b) or "[tu link de portafolio]"
        projects_hint = (
            "agrúpalos por TIPOLOGÍA / tema del dominio. Para cada proyecto: título · "
            "tipología · año · rol · 1 línea de descripción · 2–3 bullets de tu aportación · "
            "una galería de IMÁGENES (placeholders si aún no las subes) · link al proyecto si "
            "existe. La imagen manda: que se vea el trabajo, no solo el texto."
        )
        proof_section = (
            "GALERÍA VISUAL + ENLACES EXTERNOS — una rejilla de imágenes de los proyectos y, "
            f"bien visibles, los enlaces a tu portafolio externo / Behance / Issuu / sitio: {ext}. "
            "En este dominio la prueba es la IMAGEN y el portafolio enlazado: no incluyas "
            "secciones de código ni enlaces a hosting de repositorios."
        )
        stack_section = (
            "- Stack del SITIO: libre y ligero (un generador estático o un constructor visual "
            "está bien). Sin mandato de framework. Prioriza carga rápida de imágenes, "
            "responsive y un lightbox para ver los proyectos en grande.\n"
            "- Tipografía con buena jerarquía, mucho espacio en blanco; el contenido visual primero."
        )
        return projects_hint, proof_section, stack_section
    if proof_source == "none":
        projects_hint = (
            "agrúpalos por TEMA del dominio. Para cada proyecto: título · categoría · año · "
            "resumen 1 línea · 3 bullets de detalle · 1 línea de IMPACTO cuantificado · links si "
            "existen. El resultado primero, la técnica después."
        )
        proof_section = (
            "Sin sección de prueba dedicada (ni repos ni galería): que cada proyecto se sostenga "
            "solo en la página, con su resultado cuantificado."
        )
        stack_section = (
            "- Stack del sitio: libre y ligero. Sin mandato de framework. Rápido, mobile-first, "
            "accesible (semántico, headings claros para ATS/IA)."
        )
        return projects_hint, proof_section, stack_section
    # default: github / code-first proof
    projects_hint = (
        "agrúpalos por TEMA. Para cada proyecto usa SIEMPRE la misma tarjeta: título · "
        "categoría · año · resumen 1 línea · 3 bullets de detalle · 1 línea de IMPACTO "
        "cuantificado en negrita · chips de stack · links (repo/demo si existe). El resultado "
        "va PRIMERO, luego la técnica. 3–5 proyectos profundos > 15 superficiales."
    )
    proof_section = (
        "PROYECTOS/PRUEBA autocontenidos en la página: el reclutador no debería tener que entrar "
        "a un repo. Si tienes repos o demos en vivo, enlázalos por proyecto."
    )
    stack_section = (
        "- Stack del sitio: libre y ligero (cualquier framework moderno sirve). Sin librerías "
        "pesadas innecesarias. Rápido, mobile-first, accesible (semántico, headings claros para "
        "ATS/IA). Entrega la estructura de archivos completa + cómo correrlo y desplegarlo."
    )
    return projects_hint, proof_section, stack_section


def build_portfolio_prompt(
    cv: dict,
    *,
    layout: dict | None = None,
    criteria: Criteria | None = None,
    ontology: dict[str, list[str]] | None = None,
) -> str:
    """Return a long, copy-paste-ready prompt for an LLM to build the user's portfolio site.

    Domain-driven: `layout` (cv_layout.yaml) supplies the proof_source that decides whether the
    portfolio is code-first (github) or visual-first (visual_gallery); `criteria` supplies the
    role vocabulary / domain descriptor used as fallbacks and to guide skill grouping. All are
    optional — omitting them preserves the legacy data behavior.
    """
    b = cv.get("basics", {}) or {}
    proof_source = (layout or {}).get("proof_source", "github")

    name = b.get("name") or "[tu nombre]"
    role = _target_role(b, criteria)
    summary = _clean(b.get("summary"))
    skills = ", ".join(cv.get("skills") or [])
    links = _links_block(b)
    education = _education_block(cv)
    experience = _experience_block(cv)
    domain = _domain_descriptor(criteria)
    # Canonical skills from the ontology give the LLM a vocabulary to group by, domain-agnostic.
    canonical = ", ".join(list(ontology or {})[:24])

    projects_hint, proof_section, stack_section = _proof_guidance(proof_source, b)

    domain_line = f"\nDominio / familia de roles objetivo: {domain}" if domain else ""
    canonical_line = (
        f"\nVocabulario de skills del dominio (para agruparlas, no para inventarlas): {canonical}"
        if canonical
        else ""
    )

    return f"""\
Actúa como un ingeniero front-end senior + diseñador de producto. Vas a construir mi **sitio de
portafolio personal** (one-page, responsive, listo para producción). Es para conseguir un rol de
**{role}**, así que el copy del sitio va en **inglés** (con un toggle opcional ES) salvo que mi
dominio sea claramente local.

═══════════════════════════════════════════════════════════════════════
MIS DATOS REALES (usa SOLO esto; nunca inventes métricas, empresas ni experiencia)
═══════════════════════════════════════════════════════════════════════
Nombre: {name}
Título objetivo (hero): {role}{domain_line}
Links: {links}
Posicionamiento (resumen): {summary}

Skills (agrúpalas TÚ por dominio en 3–5 grupos coherentes, a partir de mis skills reales y del
vocabulario de abajo — no impongas categorías ajenas a mi campo):{canonical_line}
{skills}

Experiencia (usa los logros tal cual; puedes reescribir el wording pero NO el hecho):
{experience}

Educación / certificaciones: {education}

═══════════════════════════════════════════════════════════════════════
ESTRUCTURA EXACTA DEL PORTAFOLIO (en este orden)
═══════════════════════════════════════════════════════════════════════
1. HERO: mi nombre + el título objetivo EXACTO ("{role}") + una sola línea de posicionamiento
   centrada en el OUTCOME que genero en MI campo. Dos CTAs: "View projects" y "Get in touch".
   Botón de "Download CV".
2. STAT BAR (chips de credibilidad, SOLO números reales tomados de mi resumen y mi experiencia
   de arriba): años de experiencia, métricas/hechos cuantificados, modalidad, idiomas. No
   inventes cifras: usa únicamente las que aparecen en mis datos.
3. ABOUT: 3–4 frases humanas y concretas a partir de mi resumen, ubicación e historia profesional
   (origen, ciudad, idiomas, trayectoria). Nombra mis empresas/estudios reales como prueba social.
   Incluye foto.
4. SKILLS por dominio (3–5 grupos), no una nube plana.
5. PROYECTOS (el centro) — {projects_hint}
6. {proof_section}
7. EXPERIENCE + EDUCATION (estilo CV, conciso).
8. CONTACT: usa SOLO los canales que aparecen en mis Links de arriba (no asumas ningún canal
   que no esté listado). Repite el CTA "Let's talk".

═══════════════════════════════════════════════════════════════════════
DISEÑO Y STACK
═══════════════════════════════════════════════════════════════════════
{stack_section}
- Minimal, contenido primero, mucho espacio en blanco, jerarquía tipográfica fuerte.
- Toggle claro/oscuro. Animaciones sutiles (fade/slide), nada recargado.

═══════════════════════════════════════════════════════════════════════
LO QUE HACEN LOS MEJORES (inspírate en esto, no copies)
═══════════════════════════════════════════════════════════════════════
- Cuantifica lo cuantificable (%, $, tiempo, usuarios, m², escala). Resultado primero.
- "Last updated" por proyecto = portafolio vivo. Foto real + algo de personalidad en el About.
- Evita: proyectos flacos sin contexto, bios vagas, links rotos.

═══════════════════════════════════════════════════════════════════════
ENTREGABLE
═══════════════════════════════════════════════════════════════════════
Primero hazme 3–5 preguntas para llenar los huecos (qué proyectos reales destaco, métricas/hechos
exactos, si tengo demos o imágenes, foto). Luego genera el sitio completo, listo para correr, y
dime cómo desplegarlo con mi dominio.
"""
