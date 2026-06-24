"""Curated, verified reference portfolios + the cross-cutting patterns that make them good.

Researched and quality-vetted (dead links and thin/template sites discarded) for a Senior
Data Scientist / AI Engineer pivoting toward GenAI, with a retention/experimentation/
e-commerce focus. This is reference material the user reviews before commissioning their own
portfolio — Atlas never clones a peer's site, it only points at the live link + what to learn.
"""

from __future__ import annotations

# Each entry: a real, verified-live portfolio + an honest read of why it's worth modelling.
PEER_EXAMPLES: list[dict] = [
    {
        "peer_name": "Bjorn Melin",
        "url": "https://bjornmelin.io",
        "role_match": "Casi exacto: se titula 'Senior Data Scientist & AI Engineer' (GenAI, "
        "ML infra, cloud) — el mismo puesto que buscas.",
        "key_strengths": [
            "Proyectos con señal dura: estrellas de GitHub, specs técnicas, nº de ADRs, fechas",
            "Skills agrupadas por dominio (AI/ML, cloud, lenguajes, técnicas DS)",
            "Cada proyecto con link a GitHub + demo en vivo y chips de credibilidad arriba",
        ],
        "what_to_steal": [
            "Abrir con el título exacto del puesto + una línea de posicionamiento",
            "Una sección de 'AI builds' separada de la de analítica, para que el pivote a IA se vea",
            "Fecha de 'última actualización' por proyecto: señala un portafolio vivo",
        ],
    },
    {
        "peer_name": "Anton Ruberts",
        "url": "https://antonsruberts.github.io/",
        "role_match": "El mejor match de DOMINIO: ML aplicado a métricas de negocio — "
        "segmentación, LTV, A/B testing y causal inference. Justo tu terreno.",
        "key_strengths": [
            "Posts enmarcados como problemas de negocio reales (CLV, segmentación, A/B), no Kaggle",
            "Profundidad de herramientas (CausalML, Featuretools) atada a resultados",
            "Cada post sirve a la vez de proyecto y de liderazgo de opinión",
        ],
        "what_to_steal": [
            "Agrupar proyectos por tema de negocio: Retención, Experimentación, Automatización GenAI",
            "Un case study estrella de A/B testing / causal inference — casi nadie en LatAm lo muestra",
            "Formato 'post = case study' para que cada proyecto rinda doble (SEO + autoridad)",
        ],
    },
    {
        "peer_name": "M. I. Sezer",
        "url": "https://www.imsezer.com",
        "role_match": "ML/AI engineer (edge inference, LLM pipelines, visión). Gran match de "
        "diseño moderno + ingeniería de IA — y usa tu mismo stack (Next.js/Tailwind/Geist).",
        "key_strengths": [
            "Barra de stats arriba ('13+ modelos en producción', premios) = credibilidad instantánea",
            "Plantilla de tarjeta de proyecto consistente: título·categoría·año·bullets·impacto·stack·links",
            "Estética sobria y moderna (Next.js + Tailwind + Geist), tipografía fuerte",
        ],
        "what_to_steal": [
            "Una barra de stats con 3–4 números (A/B tests, apps de IA, 0→40k usuarios, años en remoto)",
            "Estandarizar TODA tarjeta de proyecto al mismo esqueleto",
            "Estética sobria Next.js/Tailwind (encaja con tu design system Geist)",
        ],
    },
    {
        "peer_name": "Shaw Talebi — example portfolio (plantilla)",
        "url": "https://shawhint.github.io/example-portfolio/",
        "role_match": "DS/AI; su plantilla minimal y copiable en GitHub Pages, referencia "
        "canónica de 'un portafolio de data scientist bien hecho'.",
        "key_strengths": [
            "Una sola página estilo CV (Skills → Educación → Experiencia → Proyectos → Charlas)",
            "Cada proyecto es un mini case study autocontenido con resultado cuantificado + imagen",
            "Se ve creíble sin framework pesado (GitHub Pages gratis)",
        ],
        "what_to_steal": [
            "El orden de secciones como backbone seguro",
            "Cada proyecto autocontenido en la página: problema·método·1 resultado en negrita·1 visual",
            "Frase del proyecto con el resultado PRIMERO, luego el método",
        ],
    },
    {
        "peer_name": "Shawhin Talebi — sitio de marca personal",
        "url": "https://www.shawhintalebi.com/",
        "role_match": "Practicante-educador de IA/LLM (ex-Toyota DS, PhD). Modelo de cómo "
        "presentar autoridad en IA más allá de un CV.",
        "key_strengths": [
            "Flujo narrativo (propuesta de valor → problema → solución → bio → prueba social → CTA)",
            "Credibilidad concreta: empresas y métricas nombradas, no adjetivos vagos",
            "CTAs de baja fricción repetidos a lo largo de la página",
        ],
        "what_to_steal": [
            "Un bloque 'qué hago / a quién ayudo' arriba, enmarcado por el OUTCOME (retención/AOV/CVR)",
            "Nombrar empresas y métricas reales (las tuyas, de tu experiencia) como prueba social",
            "2–3 CTAs idénticos de 'hablemos' repartidos, no solo en el footer",
        ],
    },
    {
        "peer_name": "James Le",
        "url": "https://jameskle.com/",
        "role_match": "Data → DS → ML research → DevRel; modelo de 'practicante + escritor + "
        "speaker' si quieres sumar liderazgo de opinión.",
        "key_strengths": [
            "Todo organizado en pilares claros (Portfolio, Research, Writing, Talks)",
            "Sustancia verificable: 200+ artículos, charlas, podcast",
            "Diseño editorial con foto personal — se siente humano, no plantilla",
        ],
        "what_to_steal": [
            "Pocos pilares en el home (Proyectos · Escritura · Sobre mí · Contacto) que escalen",
            "Una sección 'Notas/Escritura' con 2–3 posts (un write-up de A/B testing o LLMs)",
            "Toques editoriales (foto real, algo de personalidad)",
        ],
    },
    {
        "peer_name": "Yu Dong (DongDataDive)",
        "url": "https://yudong-94.github.io/personal-website/",
        "role_match": "Data scientist / storyteller que sumó contenido de IA/LLM a un "
        "portafolio de analítica y viz — cercano a tu trayectoria analítica→GenAI.",
        "key_strengths": [
            "Home basado en tarjetas que enruta a tipos de contenido (Vizzes, Articles, Notes)",
            "Cadencia visible (piezas semanales desde 2018) como señal de constancia",
            "Narrativa explícita de evolución analítica→IA",
        ],
        "what_to_steal": [
            "Una sección 'Notas / Aprendiendo' para hacer legible tu pivote a IA/LLM",
            "Home de tarjetas que enrute a Proyectos / Escritura / Sobre mí",
            "Mostrar cadencia: una lista fechada de trabajo reciente",
        ],
    },
    {
        "peer_name": "Mihir Chauhan",
        "url": "https://chauhan-mihir.vercel.app",
        "role_match": "ML/AI engineer 'production end-to-end'. Incluido sobre todo por su VOZ "
        "y copy — con una advertencia.",
        "key_strengths": [
            "Voz memorable: 'I build AI systems that survive contact with production'",
            "Personalidad en el 'About' sin perder profesionalismo",
            "Marco de honestidad ('nada inventado') que da confianza",
        ],
        "what_to_steal": [
            "Una línea de posicionamiento afilada en vez de 'data scientist apasionado'",
            "Un 'Sobre mí' humano y concreto (origen, ciudad, idiomas, trayectoria)",
            "⚠️ Anti-patrón: sus proyectos son flacos (claims sin detalle). Haz lo contrario.",
        ],
    },
    {
        "peer_name": "Maxime Haegeman",
        "url": "https://www.maximehaegeman.com",
        "role_match": "Senior Data/ML Engineer (Airflow, Databricks, Snowflake, dbt). Solapa "
        "tu lado de analytics engineering.",
        "key_strengths": [
            "Hero 'bio-as-code' (formato de clase de Python) memorable",
            "Matriz de skills con peso de ingeniería (diferencia 'engineer' de 'analista de notebooks')",
            "Layout minimal y enfocado, CV a un clic",
        ],
        "what_to_steal": [
            "Un toque creativo 'bio-as-code' en el hero (un dict de Python con rol/stack/ubicación)",
            "Un bloque de skills con peso de ingeniería (SQL, dbt, BigQuery, Redshift, Athena, orquestación)",
            "⚠️ Anti-patrón: sus proyectos son one-liners sin métricas. Conserva el diseño, suma profundidad.",
        ],
    },
]

# What the best DS/AI portfolios consistently do — the playbook behind the examples above.
PORTFOLIO_PATTERNS: dict[str, list[str]] = {
    "secciones": [
        "Hero: nombre + título EXACTO del puesto objetivo + una línea de posicionamiento (a quién "
        "ayudas / qué outcome generas) + foto",
        "Barra de stats / chips de credibilidad bajo el hero (años, apps de IA, 0→40k usuarios, certs)",
        "Sobre mí: narrativa corta con credibilidad concreta (empresas, métricas, contexto)",
        "Skills agrupadas por dominio (Analítica · Data/Analytics Engineering · GenAI/LLM · Viz/BI)",
        "Proyectos / Trabajo seleccionado (el centro) — agrupados por tema",
        "Escritura / Notas / Charlas (opcional, pero diferencia)",
        "Experiencia / Educación (estilo CV, conciso)",
        "Contacto + CV descargable + CTA",
    ],
    "como_mostrar_proyectos": [
        "Autocontenido en la página: problema en 1 línea · método/stack · UN resultado cuantificado en "
        "negrita · un visual — el reclutador no debería tener que entrar a GitHub",
        "Plantilla de tarjeta consistente: título · categoría · año · resumen · 3 bullets · 1 línea de "
        "impacto · chips de stack · links a repo/demo",
        "Resultado PRIMERO, luego la técnica (fórmula: técnica + métrica del modelo + resultado de negocio)",
        "Agrupar por tema/especialidad (Retención, Experimentación, Automatización GenAI), no una lista plana",
        "Cuantificar siempre (%, $, tiempo, usuarios, AUC) — 3–5 proyectos profundos > 15 notebooks flacos",
    ],
    "diseno": [
        "Minimal, contenido primero, mucho espacio en blanco",
        "Stack moderno donde importa el diseño (Next.js + Tailwind + Geist) — encaja con tu design system",
        "Toggle claro/oscuro (se lee como 'developer-savvy')",
        "Tipografía fuerte y jerarquía visual clara; foto real y algo de personalidad",
        "Rápido, mobile-friendly, sin links rotos; estructura legible también para parsers/ATS",
    ],
    "errores_a_evitar": [
        "Proyectos 'flacos': solo títulos y claims sin métricas ni arquitectura (el fallo más común)",
        "Landing genérica de plantilla que no muestra trabajo real",
        "Datasets de juguete sin marco de negocio; presumir solo 'accuracy' sin contexto",
        "Dejar pudrir el dominio/links (certificados o dominios vencidos matan la credibilidad)",
        "Una lista de proyectos plana sin agrupar ni señal de especialización",
        "Bio vaga ('experimentado, apasionado') sin empresas, métricas ni especificidad",
    ],
}
