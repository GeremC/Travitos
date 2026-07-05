"""Détection des ATS (plateformes de recrutement) et récupération des offres
via leurs endpoints JSON publics quand ils existent.
"""

import logging
import re

import config
from jobscraper.fetch import Fetcher

log = logging.getLogger("jobscraper.ats")

# ats -> regex qui capture l'identifiant de l'entreprise sur la plateforme
PATTERNS = {
    "recruitee": re.compile(r"https?://([\w-]+)\.recruitee\.com", re.I),
    "teamtailor": re.compile(r"https?://([\w-]+)\.teamtailor\.com", re.I),
    "greenhouse": re.compile(r"boards\.greenhouse\.io/([\w-]+)", re.I),
    "lever": re.compile(r"jobs\.lever\.co/([\w-]+)", re.I),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([\w-]+)", re.I),
    "smartrecruiters": re.compile(
        r"(?:careers|jobs)\.smartrecruiters\.com/([\w-]+)", re.I),
    "wttj": re.compile(
        r"welcometothejungle\.com/(?:fr|en)/companies/([\w-]+)", re.I),
    "flatchr": re.compile(r"https?://([\w-]+)\.flatchr\.io", re.I),
}


def detecter(html: str | None) -> tuple[str, str] | None:
    """Retourne (ats, identifiant) si un lien vers un ATS connu est présent."""
    if not html:
        return None
    for ats, pattern in PATTERNS.items():
        m = pattern.search(html)
        if m:
            slug = m.group(1)
            if slug.lower() in ("www", "app", "api", "static", "cdn"):
                continue
            return ats, slug
    return None


def offres(fetcher: Fetcher, ats: str, slug: str) -> list[dict] | None:
    """[{titre, url, lieu}] via l'API JSON publique de l'ATS, ou None si cet
    ATS n'en a pas (on retombe alors sur le parsing HTML générique)."""
    ttl = config.CACHE_TTL_OFFRES_J  # les offres du jour au scan du lendemain
    try:
        if ats == "recruitee":
            data = fetcher.get_json(f"https://{slug}.recruitee.com/api/offers/",
                                    ttl_j=ttl)
            if data:
                return [{"titre": o.get("title", ""),
                         "url": o.get("careers_url", ""),
                         "lieu": o.get("location") or o.get("city") or ""}
                        for o in data.get("offers", [])]
        elif ats == "greenhouse":
            data = fetcher.get_json(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                ttl_j=ttl)
            if data:
                return [{"titre": j.get("title", ""),
                         "url": j.get("absolute_url", ""),
                         "lieu": (j.get("location") or {}).get("name", "")}
                        for j in data.get("jobs", [])]
        elif ats == "lever":
            data = fetcher.get_json(
                f"https://api.lever.co/v0/postings/{slug}?mode=json",
                ttl_j=ttl)
            if isinstance(data, list):
                return [{"titre": j.get("text", ""),
                         "url": j.get("hostedUrl", ""),
                         "lieu": (j.get("categories") or {}).get("location", "")}
                        for j in data]
        elif ats == "ashby":
            data = fetcher.get_json(
                f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                ttl_j=ttl)
            if data:
                return [{"titre": j.get("title", ""),
                         "url": j.get("jobUrl", ""),
                         "lieu": j.get("location", "")}
                        for j in data.get("jobs", [])]
        elif ats == "smartrecruiters":
            data = fetcher.get_json(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                ttl_j=ttl)
            if data:
                return [{"titre": j.get("name", ""),
                         "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                         "lieu": ((j.get("location") or {}).get("city") or "")}
                        for j in data.get("content", [])]
    except Exception as e:
        log.debug("ATS %s/%s : %s", ats, slug, e)
    return None  # teamtailor, wttj, flatchr -> parsing HTML générique
