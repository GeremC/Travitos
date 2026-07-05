"""Étapes 2 & 3 — Trouver le site officiel d'une entreprise puis sa page
carrières (ou son ATS).
"""

import logging
import re
import unicodedata
import urllib.parse

from bs4 import BeautifulSoup

import config
from jobscraper import ats
from jobscraper.fetch import Fetcher, domaine, domaine_blackliste, racine

log = logging.getLogger("jobscraper.careers")

_ATS_DOMAINES = ("recruitee.com", "teamtailor.com", "greenhouse.io",
                 "lever.co", "ashbyhq.com", "smartrecruiters.com",
                 "welcometothejungle.com", "flatchr.io")


def _sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _texte_carrieres(texte: str) -> bool:
    t = _sans_accents(texte)
    return any(mot in t for mot in config.MOTS_CARRIERES)


_MOTS_VIDES = {"de", "la", "le", "les", "du", "des", "et", "en", "d", "l",
               "groupe", "cie", "compagnie"}


def _mots_significatifs(nom: str) -> list[str]:
    from jobscraper.discovery import nom_normalise
    sans_sigle = re.sub(r"\(.*?\)", " ", nom or "")
    return [m for m in nom_normalise(sans_sigle).split()
            if m not in _MOTS_VIDES and len(m) >= 2]


def _page_mentionne(html: str | None, nom: str) -> bool:
    """Garde-fou contre les mauvais résultats de recherche : le site n'est
    accepté que s'il mentionne le nom de l'entreprise."""
    if not html:
        return False
    mots = _mots_significatifs(nom)
    if not mots:
        return False
    texte = _sans_accents(html[:120000])
    compact = re.sub(r"[^a-z0-9]", "", texte)
    return ("".join(mots) in compact
            or all(m in texte for m in mots[:3]))


def _deviner_site(fetcher: Fetcher, ent: dict) -> str | None:
    """Essaie nom-de-l-entreprise.fr/.com/.eu avant tout moteur de recherche
    (les moteurs bloquent vite, pas les sites des entreprises)."""
    mots = _mots_significatifs(ent["nom"])
    if not mots:
        return None
    slugs = []
    colle = "".join(mots)
    if 4 <= len(colle) <= 25:
        slugs.append(colle)
    if len(mots) > 1 and len("-".join(mots)) <= 30:
        slugs.append("-".join(mots))
    if len(mots[0]) >= 5:
        slugs.append(mots[0])
    essais = 0
    for slug in dict.fromkeys(slugs):
        for tld in (".fr", ".com", ".eu"):
            if essais >= 6:
                return None
            essais += 1
            url = f"https://{slug}{tld}"
            info = fetcher.info(url, timeout=(5, 10))
            if (info.get("ok") and info.get("text")
                    and not domaine_blackliste(info.get("url_finale") or url)
                    and _page_mentionne(info["text"], ent["nom"])):
                return racine(info.get("url_finale") or url)
    return None


def trouver_site(fetcher: Fetcher, ent: dict) -> None:
    """Trouve le site officiel : domaine deviné, sinon moteur de recherche."""
    if ent.get("site"):
        return
    site = _deviner_site(fetcher, ent)
    if site:
        ent["site"] = site
        return
    nom_requete = re.sub(r'[()"«»]', " ", ent["nom"])
    requete = " ".join(f'{nom_requete} {ent.get("ville", "")} site officiel'.split())
    for r in fetcher.recherche(requete, max_resultats=6):
        url = r["url"]
        dom = domaine(url)
        if any(a in dom for a in _ATS_DOMAINES):
            # le résultat est déjà une page carrières hébergée
            ent["page_carrieres"] = url
            continue
        if domaine_blackliste(url):
            continue
        # validation anti-faux-positifs (les moteurs renvoient parfois
        # des résultats sans rapport quand ils soupçonnent un robot)
        html = fetcher.get(racine(url))
        if _page_mentionne(html, ent["nom"]):
            ent["site"] = racine(url)
            return


def _liens_carrieres_dans(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    candidats = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urllib.parse.urljoin(base, href)
        if not url.startswith("http"):
            continue
        texte = a.get_text(" ", strip=True)
        chemin = _sans_accents(urllib.parse.urlsplit(url).path)
        dom = domaine(url)
        est_ats = any(x in dom for x in _ATS_DOMAINES)
        if not est_ats and domaine_blackliste(url):
            continue
        if (_texte_carrieres(texte) or _texte_carrieres(chemin) or est_ats):
            # priorité aux ATS, puis aux liens du même domaine
            prio = 0 if est_ats else (1 if dom == domaine(base) else 2)
            candidats.append((prio, url))
    candidats.sort(key=lambda c: c[0])
    return [u for _, u in candidats]


def confirme_region(fetcher: Fetcher, ent: dict) -> bool:
    """Pour les entreprises trouvées par moteur de recherche (localisation
    inconnue) : leur site doit mentionner la région toulousaine. Les moteurs
    géolocalisent leurs résultats sur l'IP, pas sur la requête."""
    for url in (ent.get("site"), ent.get("page_carrieres")):
        if not url:
            continue
        html = fetcher.get(url)
        if not html:
            continue
        texte = _sans_accents(html[:200000])
        if (any(v in texte for v in config.VILLES)
                or re.search(r"\b31\d{3}\b", texte)):
            return True
    return False


def trouver_page_carrieres(fetcher: Fetcher, ent: dict) -> None:
    """Renseigne ent['page_carrieres'] et ent['ats'] si détectable."""
    # 1) indice direct issu de la découverte par moteur de recherche
    indice = ent.get("indice_carrieres")
    if indice and (_texte_carrieres(urllib.parse.urlsplit(indice).path)
                   or any(x in domaine(indice) for x in _ATS_DOMAINES)):
        ent["page_carrieres"] = indice

    site = ent.get("site")
    html_accueil = fetcher.get(site) if site else None

    # 2) lien « recrutement / carrières / jobs » sur la page d'accueil
    if not ent.get("page_carrieres") and html_accueil:
        liens = _liens_carrieres_dans(html_accueil, site)
        if liens:
            ent["page_carrieres"] = liens[0]

    # 3) chemins classiques en dernier recours
    if not ent.get("page_carrieres") and site:
        for chemin in config.CHEMINS_CARRIERES:
            info = fetcher.info(site.rstrip("/") + chemin)
            if info.get("ok") and info.get("text") and _texte_carrieres(info["text"][:20000]):
                ent["page_carrieres"] = info.get("url_finale") or site + chemin
                break

    # 4) détection d'ATS (dans la page carrières, sinon dans l'accueil)
    html_carrieres = (fetcher.get(ent["page_carrieres"])
                      if ent.get("page_carrieres") else None)
    detection = ats.detecter(html_carrieres) or ats.detecter(html_accueil)
    if not detection and ent.get("page_carrieres"):
        detection = ats.detecter(ent["page_carrieres"])
    if detection:
        ent["ats"], ent["ats_slug"] = detection
        log.debug("%s : ATS %s (%s)", ent["nom"], *detection)
