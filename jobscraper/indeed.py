"""Étape 5b — Vérifier si une offre apparaît aussi sur Indeed.

On ne scrape pas Indeed directement (Cloudflare) : on cherche
« indeed entreprise titre » sur le web (sans opérateur site:, que Bing
refuse aux robots). L'offre est marquée `sur_indeed` si un résultat Indeed
mentionnant l'entreprise remonte.
"""

import logging
import re
import unicodedata

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


def sur_indeed(fetcher: Fetcher, ent: dict, offre: dict) -> bool:
    titre = _nettoyer(offre.get("titre", ""))
    nom = _nom_court(ent.get("nom", ""))
    if not titre or not nom:
        return False
    requete = f"indeed {nom} {titre}"
    resultats = fetcher.recherche(requete, max_resultats=6)
    # un résultat Indeed compte s'il mentionne l'entreprise OU une bonne
    # partie du titre du poste (dans le doute, on préfère écarter l'offre :
    # l'utilisateur ne veut vraiment pas de doublons d'Indeed)
    mots_nom = [m for m in _normaliser(nom).split() if len(m) >= 3]
    mots_titre = [m for m in _normaliser(titre).split() if len(m) >= 4]
    for r in resultats:
        if "indeed." not in domaine(r["url"]):
            continue
        texte_resultat = _normaliser(r["titre"] + " " + r["url"])
        if not mots_nom or any(m in texte_resultat for m in mots_nom):
            log.info("Sur Indeed : %s — %s", nom, titre)
            return True
        if mots_titre and (sum(m in texte_resultat for m in mots_titre)
                           >= max(1, len(mots_titre) // 2)):
            log.info("Sur Indeed (titre proche) : %s — %s", nom, titre)
            return True
    return False
