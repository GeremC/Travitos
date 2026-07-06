"""Étape 5b — Vérifier si une offre apparaît aussi sur Indeed.

Deux méthodes :
  1. Recherche web « indeed entreprise titre » (moteurs de recherche)
  2. Requête directe sur fr.indeed.com si les moteurs sont bloqués
L'offre est marquée `sur_indeed` dès qu'Indeed mentionne l'entreprise.
"""

import logging
import re
import unicodedata
import urllib.parse

from jobscraper.fetch import Fetcher, domaine

log = logging.getLogger("jobscraper.indeed")


def _normaliser(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _nettoyer(texte: str, longueur_max: int = 60) -> str:
    t = re.sub(r"\(?\b[hfmw]\s*/\s*[hfmw]\b\)?", " ", texte, flags=re.I)
    t = re.sub(r"\b(cdi|cdd|temps plein|full[ -]?time)\b", " ", t, flags=re.I)
    t = re.sub(r"[|•·–—:!?]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:longueur_max]


def _nom_court(nom: str) -> str:
    nom = re.sub(r"\b(sasu|sas|sarl|eurl|sa|scop|scic)\b", " ", nom, flags=re.I)
    return re.sub(r"\s+", " ", nom).strip()


def _trouve_nom_dans_texte(nom_normalise: str, mots_nom: list[str],
                           texte: str) -> bool:
    """Vérifie si le nom ou ses mots significatifs apparaissent dans le texte."""
    if not mots_nom:
        return False
    if nom_normalise[:10] in texte:
        return True
    return any(m in texte for m in mots_nom[:3])


def sur_indeed(fetcher: Fetcher, ent: dict, offre: dict) -> str | None:
    """Retourne l'URL Indeed de l'offre, ou None si introuvable sur Indeed."""
    titre = _nettoyer(offre.get("titre", ""))
    nom = _nom_court(ent.get("nom", ""))
    if not titre or not nom:
        return None

    mots_nom = [m for m in _normaliser(nom).split() if len(m) >= 3]
    mots_titre = [m for m in _normaliser(titre).split() if len(m) >= 4]
    nom_norm = _normaliser(nom)

    # Méthode 1 : recherche web (existante)
    requete = f"indeed {nom} {titre}"
    resultats = fetcher.recherche(requete, max_resultats=6)
    for r in resultats:
        if "indeed." not in domaine(r["url"]):
            continue
        texte_resultat = _normaliser(r["titre"] + " " + r["url"])
        if (mots_nom and any(m in texte_resultat for m in mots_nom)) or \
           (mots_titre and sum(m in texte_resultat for m in mots_titre)
            >= max(1, len(mots_titre) // 2)):
            log.info("Sur Indeed (recherche) : %s — %s", nom, titre)
            return r["url"]

    # Méthode 2 : requête directe fr.indeed.com (contourne les moteurs bloqués)
    if not mots_nom:
        return None
    url_indeed = (
        f"https://fr.indeed.com/jobs?q={urllib.parse.quote(titre)}"
        f"&l=Toulouse&vjk={urllib.parse.quote(nom[:20])}")
    info = fetcher.info(url_indeed, timeout=(10, 20), ttl_j=0.5)
    html = info.get("text")
    if html and len(html) > 3000:
        t = _normaliser(html[:200000])
        if _trouve_nom_dans_texte(nom_norm, mots_nom, t):
            log.info("Sur Indeed (direct) : %s — %s", nom, titre)
            return url_indeed
    return None
