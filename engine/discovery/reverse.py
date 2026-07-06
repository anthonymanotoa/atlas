"""Reverse ATS discovery (F3 §6.5) — probing de empresas candidatas contra boards públicos.

HONESTIDAD: ningún ATS publica un directorio global por keyword. Lo público y keyless es
el board de CADA empresa si conoces su token (los mismos endpoints que consume
engine/discovery/ats/*). Modelo: lista de candidatas (seeds del dominio + input del
usuario) → tokens plausibles → probar Greenhouse/Lever/Ashby → sugerir solo las que
tengan posiciones que matcheen los role_terms del perfil. El usuario confirma en la UI
y save_company() las añade a companies.yaml.
"""

from __future__ import annotations

import re

import httpx

from engine.config import Criteria, load_companies
from engine.discovery.http import get_json, make_client
from engine.normalize import norm_company

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def slug_candidates(name: str) -> list[str]:
    """Tokens plausibles a partir del nombre: 'Acme Corp' → acmecorp, acme-corp, acme."""
    base = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    if not base:
        return []
    out: list[str] = []
    for cand in (base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0]):
        if cand and cand not in out:
            out.append(cand)
    return out


def _titles(ats: str, data: object) -> list[str]:
    if ats == "greenhouse":
        return [j.get("title", "") for j in (data or {}).get("jobs", [])]  # type: ignore[union-attr]
    if ats == "lever":
        return [p.get("text", "") for p in (data if isinstance(data, list) else [])]
    return [j.get("title", "") for j in ((data or {}).get("jobs") or [])]  # type: ignore[union-attr]


def probe_company(name: str, client: httpx.Client | None) -> dict | None:
    """Prueba cada ATS con los tokens plausibles; primer board con jobs gana."""
    probes: list[tuple[str, str, dict | None]] = []
    for token in slug_candidates(name):
        probes.append(("greenhouse", GREENHOUSE_URL.format(token=token), None))
        probes.append(("lever", LEVER_URL.format(token=token), {"mode": "json", "limit": 100}))
    compact = re.sub(r"[^A-Za-z0-9]", "", name)
    for token in dict.fromkeys([compact, compact.lower()]):  # Ashby es case-sensitive
        if token:
            probes.append(("ashby", ASHBY_URL.format(token=token), None))
    for ats, url, params in probes:
        try:
            data = get_json(client, url, params=params, retries=0)
        except httpx.HTTPError:
            continue
        titles = [t for t in _titles(ats, data) if t]
        if titles:
            token = (
                url.rstrip("/").split("/")[-1]
                if ats != "greenhouse"
                else url.split("/boards/")[1].split("/")[0]
            )
            return {
                "company": name,
                "ats": ats,
                "token": token,
                "jobs_count": len(titles),
                "titles": titles,
            }
    return None


def suggest_companies(
    names: list[str],
    criteria: Criteria,
    *,
    client: httpx.Client | None = None,
    max_names: int = 15,
) -> list[dict]:
    """Sugerencias {company, ats, token, jobs_count, matching_titles} para companies.yaml."""
    known = {norm_company(c.company) for c in load_companies()}
    clean = [n.strip() for n in names if n and n.strip()]
    candidates = [n for n in dict.fromkeys(clean) if norm_company(n) not in known][:max_names]
    owns = client is None and bool(candidates)
    if owns:
        client = make_client(timeout=10)
    terms = criteria.all_role_terms
    out: list[dict] = []
    try:
        for name in candidates:
            hit = probe_company(name, client)
            if not hit:
                continue
            matching = [t for t in hit["titles"] if any(term in t.lower() for term in terms)]
            if not matching:
                continue
            out.append(
                {
                    "company": name,
                    "ats": hit["ats"],
                    "token": hit["token"],
                    "jobs_count": hit["jobs_count"],
                    "matching_titles": matching[:5],
                }
            )
    finally:
        if owns and client is not None:
            client.close()
    return out
