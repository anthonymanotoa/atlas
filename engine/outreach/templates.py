"""Outreach draft templates (EN/ES), encoding the research-backed best practices.

Priority ladder (referral → warm intro → InMail → cold email) is handled by the brain;
this module produces the actual short, specific, on-voice drafts:
  • cold email 75–100 words, 4-part, soft open-ended CTA, ≤125 hard cap
  • LinkedIn connection note 120–180 chars, NO pitch (the ask comes after they accept)
  • recruiter = req-fit + logistics; hiring manager = team-problem + contribution
  • referral ask = forward-ready package + explicit easy-out
These are baselines; the Cowork LLM sharpens them in the user's voice before drafting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Draft:
    kind: str  # cover_letter | recruiter | hiring_manager | referral_ask | cold_email | linkedin_note | follow_up | breakup
    channel: str  # email | linkedin_note | linkedin_inmail | referral
    body: str
    subject: str | None = None
    variant: str | None = None
    language: str = "en"


def _first_name(name: str | None) -> str:
    return (name or "").split()[0] if name else ""


def _word_cap(text: str, max_words: int = 125) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]).rstrip(",.;") + "…"


_ACRONYMS = {
    "ml",
    "ai",
    "llm",
    "llms",
    "sql",
    "aws",
    "gcp",
    "nlp",
    "rag",
    "etl",
    "bi",
    "api",
    "dl",
    "gpu",
    "mlops",
}


def _pretty(skill: str) -> str:
    out = []
    for w in skill.split():
        if w.lower() in _ACRONYMS:
            out.append(w.upper())
        elif "/" in w:
            out.append(w.upper())  # a/b -> A/B
        elif w.islower():
            out.append(w.capitalize())
        else:
            out.append(w)  # preserve given casing (AutoCAD, BIM, ArchiCAD, McKinsey)
    return " ".join(out)


def _skills_phrase(matched: list[str], n: int = 3, language: str = "en") -> str:
    top = [_pretty(s) for s in matched[:n]]
    if not top:
        return "mis competencias clave" if language == "es" else "my core skills"
    joiner = " y " if language == "es" else " and "
    if len(top) == 1:
        return top[0]
    return ", ".join(top[:-1]) + joiner + top[-1]


def _pitch_of(candidate: dict) -> dict:
    """Resolve the candidate's outreach 'pitch' with domain-neutral fallbacks from the headline.

    pitch = {identity_line, role_noun, impact_domain, value_verb}. Absent fields fall back to the
    CV headline so non-data candidates never inherit the old 'senior data scientist' persona."""
    p = candidate.get("pitch") or {}
    headline = (candidate.get("headline") or "").strip()
    role_noun = (p.get("role_noun") or headline or "professional").strip()
    return {
        "role_noun": role_noun,
        "identity_line": (p.get("identity_line") or headline or f"a {role_noun}").strip(),
        "impact_domain": (p.get("impact_domain") or "").strip(),
        "value_verb": (p.get("value_verb") or "").strip(),
    }


def build_package(
    job: dict,
    candidate: dict,
    matched: list[str],
    contact: dict | None = None,
    language: str = "en",
) -> list[Draft]:
    """candidate = {name, headline, linkedin, one_liner}. Returns all draft variants."""
    company = job.get("company", "")
    role = job.get("title", "")
    me = candidate.get("name", "")
    mine = _first_name(me)
    skills = _skills_phrase(matched, language=language)
    pitch = _pitch_of(candidate)
    cname = _first_name((contact or {}).get("name"))
    li = candidate.get("linkedin", "")

    if language == "es":
        greet = f"Hola {cname}" if cname else "Hola"
        return _es(company, role, me, mine, skills, greet, li, contact, pitch)
    greet = f"Hi {cname}" if cname else "Hi there"
    return _en(company, role, me, mine, skills, greet, li, contact, pitch)


# ── English ───────────────────────────────────────────────────────────────────
def _en(company, role, me, mine, skills, greet, li, contact, pitch) -> list[Draft]:
    ident, rn, pd = pitch["identity_line"], pitch["role_noun"], pitch["impact_domain"]
    pv = pitch["value_verb"] or "work on"
    impact = f" In my current work I {pv} {pd}." if pd else ""
    blurb = f" {pv[0].upper()}{pv[1:]} {pd}." if pd else ""
    cover = (
        f"I'm applying for the {role} role at {company}. I'm {ident}, with strong hands-on "
        f"experience in {skills}.{impact} {company}'s focus is a strong fit for how I work. "
        f"I'd welcome the chance to discuss how I can contribute. Thank you for your "
        f"consideration.\n\n{me}\n{li}"
    )
    cold = _word_cap(
        f"{greet}, I saw the {role} opening at {company} and it lines up closely with my "
        f"background — I'm {ident}, strong in {skills}.{impact} Would it be worth a quick chat "
        f"about the role?\n\nThanks,\n{me}\n{li}"
    )
    recruiter = (
        f"{greet}, I'm interested in the {role} role at {company}. Quick fit: {rn}, strong in "
        f"{skills}, available to interview on short notice. Happy to send anything helpful for "
        f"the screen. Thanks for your time!\n\n{me}"
    )
    hm = (
        f"{greet}, I came across the {role} opening and wanted to reach out directly. I'm {ident} "
        f"— that's exactly where I add value: {skills}, with a track record of turning work into "
        f"results. I'd love to learn what success looks like for this role in the first "
        f"6 months.\n\n{me}\n{li}"
    )
    referral = (
        f"{greet}, hope you're doing well! I'm exploring a move and {company} is high on my "
        f"list — they have a {role} opening that fits me well. Would you be open to referring me "
        f"or pointing me to the right person? No pressure at all if it's not a good moment.\n\n"
        f"To make it easy, here's a blurb you can forward:\n"
        f"———\n{me} — {rn}. Strong in {skills}.{blurb} Applying for {role} at {company}. "
        f"LinkedIn: {li}\n———\n\nThank you so much,\n{mine}"
    )
    note = _linkedin_note(company, role, "en")
    return [
        Draft("cover_letter", "email", cover, subject=f"Application — {role}", language="en"),
        Draft(
            "cold_email",
            "email",
            cold,
            subject=f"{role} at {company}",
            variant="recruiter",
            language="en",
        ),
        Draft(
            "recruiter", "linkedin_inmail", recruiter, subject=f"{role} — quick fit", language="en"
        ),
        Draft(
            "hiring_manager", "linkedin_inmail", hm, subject=f"{role} on your team", language="en"
        ),
        Draft(
            "referral_ask",
            "referral",
            referral,
            subject=f"Referral for {role} at {company}?",
            language="en",
        ),
        Draft("linkedin_note", "linkedin_note", note, language="en"),
    ]


# ── Spanish ───────────────────────────────────────────────────────────────────
def _es(company, role, me, mine, skills, greet, li, contact, pitch) -> list[Draft]:
    ident, rn, pd = pitch["identity_line"], pitch["role_noun"], pitch["impact_domain"]
    pv = pitch["value_verb"] or "trabajo en"
    impact = f" En mi trabajo actual {pv} {pd}." if pd else ""
    blurb = f" {pv[0].upper()}{pv[1:]} {pd}." if pd else ""
    cover = (
        f"Me postulo a la posición de {role} en {company}. Soy {ident}, con experiencia sólida "
        f"en {skills}.{impact} El enfoque de {company} encaja muy bien con mi forma de trabajar. "
        f"Me encantaría conversar sobre cómo aportar. Gracias por su consideración.\n\n{me}\n{li}"
    )
    cold = _word_cap(
        f"{greet}, vi la vacante de {role} en {company} y encaja mucho con mi perfil: soy {ident}, "
        f"con base sólida en {skills}.{impact} ¿Valdría la pena una breve conversación?\n\n"
        f"Gracias,\n{me}\n{li}"
    )
    recruiter = (
        f"{greet}, me interesa la posición de {role} en {company}. Fit rápido: {rn}, sólido en "
        f"{skills}, disponible para entrevistar pronto. Con gusto envío lo que sea útil para el "
        f"screening. ¡Gracias por tu tiempo!\n\n{me}"
    )
    hm = (
        f"{greet}, vi la vacante de {role} y quise escribirte directamente. Soy {ident} — ahí es "
        f"justo donde aporto valor: {skills}, con historial de convertir el trabajo en resultados. "
        f"Me encantaría saber cómo se ve el éxito en este rol en los primeros 6 meses.\n\n{me}\n{li}"
    )
    referral = (
        f"{greet}, ¡espero que estés muy bien! Estoy explorando un cambio y {company} está "
        f"entre mis favoritas — tienen una vacante de {role} que encaja conmigo. ¿Estarías "
        f"dispuesto/a a referirme o indicarme a la persona indicada? Sin presión si no es buen "
        f"momento.\n\nPara hacerlo fácil, aquí va un texto que puedes reenviar:\n"
        f"———\n{me} — {rn}. Sólido en {skills}.{blurb} Postulando a {role} en {company}. "
        f"LinkedIn: {li}\n———\n\nMil gracias,\n{mine}"
    )
    note = _linkedin_note(company, role, "es")
    return [
        Draft("cover_letter", "email", cover, subject=f"Postulación — {role}", language="es"),
        Draft(
            "cold_email",
            "email",
            cold,
            subject=f"{role} en {company}",
            variant="recruiter",
            language="es",
        ),
        Draft(
            "recruiter", "linkedin_inmail", recruiter, subject=f"{role} — fit rápido", language="es"
        ),
        Draft(
            "hiring_manager", "linkedin_inmail", hm, subject=f"{role} en tu equipo", language="es"
        ),
        Draft(
            "referral_ask",
            "referral",
            referral,
            subject=f"¿Referido para {role} en {company}?",
            language="es",
        ),
        Draft("linkedin_note", "linkedin_note", note, language="es"),
    ]


def _linkedin_note(company: str, role: str, language: str) -> str:
    """120–180 char connection note — a reason to accept, no pitch."""
    if language == "es":
        note = f"Hola, sigo a {company} y vi la vacante de {role}. Me encantaría conectar y aprender más del equipo. ¡Gracias!"
    else:
        note = f"Hi — I follow {company} and saw the {role} opening. I'd love to connect and learn more about the team. Thanks!"
    if len(note) > 180:
        note = note[:177].rstrip() + "…"
    return note
