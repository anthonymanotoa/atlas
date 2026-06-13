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
from typing import Optional


@dataclass
class Draft:
    kind: str        # cover_letter | recruiter | hiring_manager | referral_ask | cold_email | linkedin_note | follow_up | breakup
    channel: str     # email | linkedin_note | linkedin_inmail | referral
    body: str
    subject: Optional[str] = None
    variant: Optional[str] = None
    language: str = "en"


def _first_name(name: Optional[str]) -> str:
    return (name or "").split()[0] if name else ""


def _word_cap(text: str, max_words: int = 125) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]).rstrip(",.;") + "…"


_ACRONYMS = {"ml", "ai", "llm", "llms", "sql", "aws", "gcp", "nlp", "rag", "etl",
             "bi", "api", "dl", "gpu", "mlops"}


def _pretty(skill: str) -> str:
    out = []
    for w in skill.split():
        if w.lower() in _ACRONYMS:
            out.append(w.upper())
        elif "/" in w:
            out.append(w.upper())          # a/b -> A/B
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _skills_phrase(matched: list[str], n: int = 3) -> str:
    top = [_pretty(s) for s in matched[:n]]
    if not top:
        return "data science and analytics"
    if len(top) == 1:
        return top[0]
    return ", ".join(top[:-1]) + f" and {top[-1]}"


def build_package(job: dict, candidate: dict, matched: list[str],
                  contact: Optional[dict] = None, language: str = "en") -> list[Draft]:
    """candidate = {name, headline, linkedin, one_liner}. Returns all draft variants."""
    company = job.get("company", "")
    role = job.get("title", "")
    me = candidate.get("name", "")
    mine = _first_name(me)
    skills = _skills_phrase(matched)
    cname = _first_name((contact or {}).get("name"))
    li = candidate.get("linkedin", "")

    if language == "es":
        greet = f"Hola {cname}" if cname else "Hola"
        return _es(company, role, me, mine, skills, greet, li, contact)
    greet = f"Hi {cname}" if cname else "Hi there"
    return _en(company, role, me, mine, skills, greet, li, contact)


# ── English ───────────────────────────────────────────────────────────────────
def _en(company, role, me, mine, skills, greet, li, contact) -> list[Draft]:
    cover = (
        f"I'm applying for the {role} role at {company}. I'm a senior data scientist "
        f"moving deeper into AI/ML, with strong hands-on experience in {skills}. In my "
        f"current role I own experimentation and analytics for high-growth e-commerce, "
        f"shipping work that drives real decisions. {company}'s focus is a strong fit for "
        f"how I work — remote, data-driven, and fast. I'd welcome the chance to discuss how "
        f"I can contribute. Thank you for your consideration.\n\n{me}\n{li}"
    )
    cold = _word_cap(
        f"{greet}, I saw the {role} opening at {company} and it lines up closely with my "
        f"background — a senior data scientist now building with AI/LLMs, strong in {skills}. "
        f"I've spent the last few years owning experimentation and analytics for high-growth "
        f"e-commerce. Would it be worth a quick chat about the role?\n\nThanks,\n{me}\n{li}"
    )
    recruiter = (
        f"{greet}, I'm interested in the {role} role at {company}. Quick fit: senior data "
        f"scientist / AI engineer, strong in {skills}, fully remote and available to interview "
        f"on short notice. Happy to send anything helpful for the screen. Thanks for your time!\n\n{me}"
    )
    hm = (
        f"{greet}, I came across the {role} opening and wanted to reach out directly. From "
        f"what I can see, your team is investing in data/AI to move faster — that's exactly "
        f"where I add value: {skills}, with a track record of turning analysis into decisions. "
        f"I'd love to learn what success looks like for this role in the first 6 months.\n\n{me}\n{li}"
    )
    referral = (
        f"{greet}, hope you're doing well! I'm exploring a move and {company} is high on my "
        f"list — they have a {role} opening that fits me well. Would you be open to referring me "
        f"or pointing me to the right person? No pressure at all if it's not a good moment.\n\n"
        f"To make it easy, here's a blurb you can forward:\n"
        f"———\n{me} — senior data scientist / AI engineer (remote). Strong in {skills}; owns "
        f"experimentation & analytics for high-growth e-commerce. Applying for {role} at {company}. "
        f"LinkedIn: {li}\n———\n\nThank you so much,\n{mine}"
    )
    note = _linkedin_note(company, role, "en")
    return [
        Draft("cover_letter", "email", cover, subject=f"Application — {role}", language="en"),
        Draft("cold_email", "email", cold, subject=f"{role} at {company}", variant="recruiter", language="en"),
        Draft("recruiter", "linkedin_inmail", recruiter, subject=f"{role} — quick fit", language="en"),
        Draft("hiring_manager", "linkedin_inmail", hm, subject=f"{role} on your team", language="en"),
        Draft("referral_ask", "referral", referral, subject=f"Referral for {role} at {company}?", language="en"),
        Draft("linkedin_note", "linkedin_note", note, language="en"),
    ]


# ── Spanish ───────────────────────────────────────────────────────────────────
def _es(company, role, me, mine, skills, greet, li, contact) -> list[Draft]:
    cover = (
        f"Me postulo a la posición de {role} en {company}. Soy data scientist senior con un "
        f"enfoque creciente en IA/ML, con experiencia sólida en {skills}. Actualmente lidero "
        f"experimentación y analítica para e-commerce de alto crecimiento, entregando trabajo "
        f"que impulsa decisiones reales. El enfoque de {company} encaja muy bien con mi forma de "
        f"trabajar: remoto, basado en datos y ágil. Me encantaría conversar sobre cómo aportar. "
        f"Gracias por su consideración.\n\n{me}\n{li}"
    )
    cold = _word_cap(
        f"{greet}, vi la vacante de {role} en {company} y encaja mucho con mi perfil: data "
        f"scientist senior que ahora construye con IA/LLMs, con base sólida en {skills}. Los "
        f"últimos años he liderado experimentación y analítica para e-commerce de alto "
        f"crecimiento. ¿Valdría la pena una breve conversación?\n\nGracias,\n{me}\n{li}"
    )
    recruiter = (
        f"{greet}, me interesa la posición de {role} en {company}. Fit rápido: data scientist "
        f"/ AI engineer senior, sólido en {skills}, 100% remoto y disponible para entrevistar pronto. "
        f"Con gusto envío lo que sea útil para el screening. ¡Gracias por tu tiempo!\n\n{me}"
    )
    hm = (
        f"{greet}, vi la vacante de {role} y quise escribirte directamente. Por lo que veo, tu "
        f"equipo está invirtiendo en datos/IA para moverse más rápido — ahí es justo donde aporto "
        f"valor: {skills}, con historial de convertir análisis en decisiones. Me encantaría saber "
        f"cómo se ve el éxito en este rol en los primeros 6 meses.\n\n{me}\n{li}"
    )
    referral = (
        f"{greet}, ¡espero que estés muy bien! Estoy explorando un cambio y {company} está "
        f"entre mis favoritas — tienen una vacante de {role} que encaja conmigo. ¿Estarías dispuesto/a "
        f"a referirme o indicarme a la persona indicada? Sin presión si no es buen momento.\n\n"
        f"Para hacerlo fácil, aquí va un texto que puedes reenviar:\n"
        f"———\n{me} — data scientist / AI engineer senior (remoto). Sólido en {skills}; lidera "
        f"experimentación y analítica para e-commerce de alto crecimiento. Postulando a {role} en "
        f"{company}. LinkedIn: {li}\n———\n\nMil gracias,\n{mine}"
    )
    note = _linkedin_note(company, role, "es")
    return [
        Draft("cover_letter", "email", cover, subject=f"Postulación — {role}", language="es"),
        Draft("cold_email", "email", cold, subject=f"{role} en {company}", variant="recruiter", language="es"),
        Draft("recruiter", "linkedin_inmail", recruiter, subject=f"{role} — fit rápido", language="es"),
        Draft("hiring_manager", "linkedin_inmail", hm, subject=f"{role} en tu equipo", language="es"),
        Draft("referral_ask", "referral", referral, subject=f"¿Referido para {role} en {company}?", language="es"),
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
