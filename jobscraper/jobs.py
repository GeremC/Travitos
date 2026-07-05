"""Étape 4 — Extraire les liens d'offres d'emploi depuis une page carrières.

Trois stratégies, dans l'ordre :
  1. API JSON de l'ATS si détecté (fiable) ;
  2. parsing HTML de la page carrières ;
  3. rendu Playwright puis parsing, si le HTML statique ne donne rien.
"""

import logging
import re
import unicodedata
import urllib.parse

from bs4 import BeautifulSoup

import config
from jobscraper import ats
from jobscraper.fetch import Fetcher, domaine, domaine_blackliste

log = logging.getLogger("jobscraper.jobs")

MOTIF_URL_OFFRE = re.compile(
    r"/(offres?|jobs?|emplois?|postes?|positions?|vacanc\w*|openings?|"
    r"annonces?|opportunit\w*|recrutements?|carrieres?|careers?)(/|-|_|\.|$)",
    re.I)
MOTIF_TEXTE_OFFRE = re.compile(
    r"\b(cdi|cdd|h\s*/\s*f|f\s*/\s*h|m\s*/\s*f|w\s*/\s*m|temps plein|"
    r"full[ -]?time|temps partiel)\b", re.I)
_EXT_IGNOREES = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".css", ".js",
                 ".ico", ".zip", ".mp4", ".webp")


def _sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    return s


def _titre_depuis_url(url: str) -> str:
    slug = urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.(html?|php|aspx?|pdf)$", "", slug, flags=re.I)
    return re.sub(r"[-_+]+", " ", urllib.parse.unquote(slug)).strip().title()


def _score_lien(url: str, texte: str, base: str) -> int:
    """Score heuristique ; 0 d'office sans signal structurel d'offre
    (CDI/H-F dans le texte, ou /offre, /job… dans l'URL), pour ne pas
    prendre les pages de services « Traduction » pour des offres."""
    chemin = urllib.parse.urlsplit(url).path
    chemin_base = urllib.parse.urlsplit(base).path.rstrip("/")
    texte_n = _sans_accents(texte)
    if not (MOTIF_TEXTE_OFFRE.search(texte) or MOTIF_URL_OFFRE.search(chemin)):
        return 0
    # filtre les textes qui ne sont pas des offres (navigation, CTA…)
    if texte_n.startswith("\u00ab"):  # « → slogan, pas une offre
        return 0
    if texte_n in config.TITRES_PAS_OFFRE_EXACTS:
        return 0
    for motif in config.TITRES_PAS_OFFRE:
        if " " in motif:
            if motif in texte_n:
                return 0
        else:
            if re.search(r"\b" + re.escape(motif) + r"\b", texte_n):
                return 0
    score = 0
    if MOTIF_TEXTE_OFFRE.search(texte):
        score += 2
    if MOTIF_URL_OFFRE.search(chemin):
        score += 1
    # le lien va plus profond que la page carrières elle-même
    if chemin.rstrip("/") != chemin_base and len(chemin) > len(chemin_base) + 3:
        score += 1
    # un identifiant ou un slug long dans l'URL sent l'offre individuelle
    if re.search(r"\d{2,}", chemin) or len(chemin.rsplit("/", 1)[-1]) > 25:
        score += 1
    for pattern, _ in config.MOTS_CLES_LINGUISTIQUE:
        if re.search(pattern, texte_n):
            score += 2
            break
    if 8 <= len(texte) <= 140:
        score += 1
    return score


def _depuis_html(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    offres, vues = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urllib.parse.urljoin(base, href)
        if not url.startswith("http") or url.split("#")[0] == base.split("#")[0]:
            continue
        if url.lower().endswith(_EXT_IGNOREES):
            continue
        dom = domaine(url)
        if domaine_blackliste(url) and "welcometothejungle" not in dom:
            continue
        texte = a.get_text(" ", strip=True)
        if _score_lien(url, texte, base) < 3:
            continue
        url_propre = url.split("#")[0]
        if url_propre in vues:
            continue
        vues.add(url_propre)
        # « Voir l'offre », « Postuler »… ou une URL brute : le slug de
        # l'URL fait un meilleur titre
        generique = re.match(
            r"^\s*(voir|voir l.offre|postuler|en savoir plus|candidater|"
            r"lire la suite|details?|https?://)", _sans_accents(texte))
        if not texte or generique:
            texte = _titre_depuis_url(url)
        offres.append({"titre": texte, "url": url_propre, "lieu": ""})
    return offres


def extraire_offres(fetcher: Fetcher, ent: dict) -> list[dict]:
    page = ent.get("page_carrieres")
    if not page:
        return []

    # 1) API JSON de l'ATS
    if ent.get("ats"):
        via_api = ats.offres(fetcher, ent["ats"], ent["ats_slug"])
        if via_api:
            return [o for o in via_api if o.get("url")][:config.MAX_OFFRES_PAR_ENTREPRISE]

    # 2) HTML statique — TTL court : les offres du jour doivent apparaître
    #    au scan quotidien suivant
    html = fetcher.get(page, ttl_j=config.CACHE_TTL_OFFRES_J)
    offres = _depuis_html(html, page) if html else []

    # 3) rendu Playwright si rien (page en JS pur)
    if not offres:
        html = fetcher.render(page, ttl_j=config.CACHE_TTL_OFFRES_J)
        if html:
            offres = _depuis_html(html, page)

    return offres[:config.MAX_OFFRES_PAR_ENTREPRISE]
