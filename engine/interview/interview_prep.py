"""Deterministic interview-prep generator (P3-E).

Builds a prep doc (likely questions + STAR answer scaffolds grounded in the user's REAL
CV) from the interview, its interviewers, the job, and any company learnings. The Cowork
session may sharpen wording, but this baseline stands alone and never fabricates experience.
"""

from __future__ import annotations

from pathlib import Path

import engine.paths as paths
from engine.config import load_master_cv
from engine.db.models import DB

_BEHAVIORAL = {
    "en": [
        "Tell me about yourself and your path toward AI/ML.",
        "Walk me through a project you're proud of — your specific contribution and its impact.",
        "Tell me about a time you disagreed with a stakeholder. How did you handle it?",
        "Describe a project that didn't go as planned. What did you learn?",
        "Why this company and this role specifically?",
    ],
    "es": [
        "Cuéntame sobre ti y tu transición hacia IA/ML.",
        "Cuéntame un proyecto del que estés orgulloso — tu aporte específico y su impacto.",
        "Háblame de una vez que no estuviste de acuerdo con un stakeholder. ¿Cómo lo manejaste?",
        "Describe un proyecto que no salió como esperabas. ¿Qué aprendiste?",
        "¿Por qué esta empresa y este rol en particular?",
    ],
}

# (keywords matched in title+desc) -> (en questions, es questions)
_ROLE_TOPICS: list[tuple[tuple[str, ...], list[str], list[str]]] = [
    (
        ("data scien", "machine learning", "ml engineer", "applied scien"),
        [
            "How do you design and read an A/B test? How do you handle peeking / multiple comparisons?",
            "How do you choose a model and decide it's good enough to ship?",
            "How do you monitor a model in production and detect drift?",
        ],
        [
            "¿Cómo diseñas y lees un A/B test? ¿Cómo manejas el peeking / comparaciones múltiples?",
            "¿Cómo eliges un modelo y decides que está listo para producción?",
            "¿Cómo monitoreas un modelo en producción y detectas drift?",
        ],
    ),
    (
        ("ai engineer", "llm", "genai", "generative", "rag", "agent"),
        [
            "How do you evaluate an LLM/RAG system beyond vibes (metrics, eval sets)?",
            "How do you control cost and latency in an LLM application?",
            "When would you fine-tune vs. prompt vs. RAG?",
        ],
        [
            "¿Cómo evalúas un sistema LLM/RAG más allá de la intuición (métricas, sets de eval)?",
            "¿Cómo controlas costo y latencia en una aplicación con LLMs?",
            "¿Cuándo harías fine-tuning vs. prompting vs. RAG?",
        ],
    ),
    (
        ("analyst", "analytics", "business intelligence", "bi "),
        [
            "Walk me through how you'd turn a vague business question into a metric + analysis.",
            "A key metric dropped 20% overnight — how do you investigate?",
        ],
        [
            "Explícame cómo convertirías una pregunta de negocio vaga en una métrica + análisis.",
            "Una métrica clave cayó 20% de un día para otro — ¿cómo investigas?",
        ],
    ),
]

_DEFAULT_TECH = {
    "en": [
        "Walk me through a recent technical problem end-to-end (data → decision → impact).",
        "How do you ensure your analysis/code is correct and reproducible?",
    ],
    "es": [
        "Explícame un problema técnico reciente de punta a punta (datos → decisión → impacto).",
        "¿Cómo te aseguras de que tu análisis/código sea correcto y reproducible?",
    ],
}

_HEAD = {
    "en": {
        "title": "Interview prep",
        "interviewers": "Interviewers",
        "behavioral": "Likely behavioral questions",
        "role": "Likely role/technical questions",
        "company": "What we've learned about this company",
        "star": "Your STAR evidence (real, from your CV — adapt, don't invent)",
        "research": "Research each interviewer (supervised, in your own browser)",
        "no_iv": "No interviewers added yet — add them in the dashboard.",
    },
    "es": {
        "title": "Preparación de entrevista",
        "interviewers": "Entrevistadores",
        "behavioral": "Preguntas conductuales probables",
        "role": "Preguntas de rol/técnicas probables",
        "company": "Lo que aprendimos de esta empresa",
        "star": "Tu evidencia STAR (real, de tu CV — adáptala, no inventes)",
        "research": "Investiga a cada entrevistador (supervisado, en tu propio navegador)",
        "no_iv": "Aún no agregaste entrevistadores — agrégalos en el dashboard.",
    },
}


def _role_questions(title: str, desc: str, lang: str) -> list[str]:
    hay = f"{title} {desc}".lower()
    out: list[str] = []
    for keywords, en_q, es_q in _ROLE_TOPICS:
        if any(k in hay for k in keywords):
            out.extend(en_q if lang == "en" else es_q)
    return out or _DEFAULT_TECH[lang]


def _star_evidence(cv: dict, lang: str) -> list[str]:
    """Real, quantified highlights from the CV the candidate can build STAR answers on."""
    out: list[str] = []
    for exp in (cv.get("experience") or [])[:3]:
        role = f"{exp.get('title', '')} @ {exp.get('company', '')}".strip(" @")
        for hl in (exp.get("highlights") or [])[:2]:
            out.append(f"[{role}] {hl}")
    return out


def gen_prep_doc(db: DB, interview_id: int, language: str = "en") -> Path:
    lang = "es" if language == "es" else "en"
    h = _HEAD[lang]
    iv = db.get_interview(interview_id)
    if not iv:
        raise ValueError(f"interview {interview_id} not found")
    job = db.get_job(iv["job_id"]) or {}
    interviewers = db.interviewers_for(interview_id)
    cv = load_master_cv()
    learnings = db.learnings_for_company(job.get("company", ""))

    title, desc = job.get("title", ""), job.get("description", "") or ""
    lines = [
        f"# {h['title']} — {title} @ {job.get('company', '')}",
        "",
        f"_{iv.get('round') or ''} · {iv.get('scheduled_at') or 'sin fecha'} · {iv.get('mode') or ''}_",
        "",
        f"## {h['interviewers']}",
    ]
    if interviewers:
        for p in interviewers:
            link = f" — {p['linkedin_url']}" if p.get("linkedin_url") else ""
            lines.append(f"- **{p.get('name', '')}** · {p.get('title') or ''}{link}")
            if p.get("research_notes"):
                lines.append(f"  - {p['research_notes']}")
    else:
        lines.append(f"_{h['no_iv']}_")
    lines += [
        "",
        f"> {h['research']}: abre cada perfil de LinkedIn a mano, lee su experiencia/posts, y "
        "anota qué temas domina para anticipar sus preguntas. (Ver docs/RATE_LIMITING.md.)",
        "",
        f"## {h['behavioral']}",
    ]
    lines += [f"- {q}" for q in _BEHAVIORAL[lang]]
    lines += ["", f"## {h['role']}"]
    lines += [f"- {q}" for q in _role_questions(title, desc, lang)]

    if learnings:
        lines += ["", f"## {h['company']}"]
        lines += [
            f"- {learning['observation']} (confianza {learning['confidence']:.0%})"
            for learning in learnings
        ]

    evidence = _star_evidence(cv, lang)
    if evidence:
        lines += ["", f"## {h['star']}"]
        lines += [f"- {e}" for e in evidence]

    out_dir = paths.OUTBOX_DIR / f"interview_{interview_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"interview_prep_{lang}.md"
    path.write_text("\n".join(lines))
    db.set_interview_prep_path(interview_id, str(path))
    return path
