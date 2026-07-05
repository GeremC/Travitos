"""Étape 5a — Scoring des offres : pertinence linguistique (prioritaire),
temps plein, localisation région toulousaine.
"""

import re
import unicodedata

import config

_REGEX_VILLES_EXCLUES = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in config.VILLES_EXCLUES) + r")\b")


def normaliser(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    return s


def score_linguistique(titre: str) -> int:
    t = normaliser(titre)
    return sum(poids for pattern, poids in config.MOTS_CLES_LINGUISTIQUE
               if re.search(pattern, t))


def est_exclue(titre: str) -> bool:
    """Stage, alternance, freelance, temps partiel… : pas un temps plein."""
    return bool(re.search(config.MOTIFS_EXCLUSION, normaliser(titre)))


def est_pas_offre(titre: str) -> bool:
    """Filtre les textes qui ne sont pas de vraies offres
    (navigation, CTA, catégories…)."""
    t = normaliser(titre)
    if t.startswith("\u00ab"):  # « → slogan, pas une offre
        return True
    if t in config.TITRES_PAS_OFFRE_EXACTS:
        return True
    for motif in config.TITRES_PAS_OFFRE:
        if " " in motif:
            if motif in t:
                return True
        else:
            if re.search(r"\b" + re.escape(motif) + r"\b", t):
                return True
    return False


def bonus_temps_plein(titre: str) -> int:
    return 3 if re.search(config.MOTIFS_TEMPS_PLEIN, normaliser(titre)) else 0


def lieu_ok(lieu: str) -> bool | None:
    """True/False si le lieu est connu, None s'il est inconnu."""
    l = normaliser(lieu)
    if not l.strip():
        return None
    if _REGEX_VILLES_EXCLUES.search(l):
        return False  # une grande ville hors zone prime sur « Occitanie »
    if any(v in l for v in config.VILLES) or re.search(r"\b31\d{3}\b", l):
        return True
    if re.search(config.MOTIFS_REMOTE, l):
        return True
    return False


def evaluer(offre: dict, ent: dict) -> dict:
    """Complète l'offre avec score, exclusion et verdict de localisation."""
    texte = f"{offre.get('titre', '')} {offre.get('lieu', '')}"
    offre["score_linguistique"] = score_linguistique(offre.get("titre", ""))
    offre["exclue"] = est_exclue(texte)
    if not offre["exclue"] and est_pas_offre(offre.get("titre", "")):
        offre["exclue"] = True
    verdict = lieu_ok(offre.get("lieu", ""))
    # une ville hors zone dans le titre prime sur tout (« Traducteur - Lyon »)
    if _REGEX_VILLES_EXCLUES.search(normaliser(offre.get("titre", ""))):
        verdict = False
    if verdict is None and ent.get("source") == "annuaire":
        verdict = True  # entreprise déjà filtrée sur le département 31
    offre["hors_zone"] = verdict is False
    offre["score"] = (offre["score_linguistique"] * 3
                      + bonus_temps_plein(texte)
                      + (2 if verdict else 0))
    return offre


# motifs « type de contrat » cherchés dans la page de l'offre elle-même
_REGEX_CONTRAT_EXCLU = re.compile(
    r"(type de contrat|contrat|contract)\s*:?\s*(de\s+|d')?"
    r"(stage|alternance|apprentissage|professionnalisation)"
    r"|\b(stage|alternance)\s+de\s+\d+\s*mois")


def verifier_page_offre(fetcher, offre: dict) -> None:
    """Ouvre la page de l'offre pour vérifier ce que le titre ne dit pas :
    le lieu réel du poste et le type de contrat (stage/alternance déguisés).
    Une entreprise toulousaine peut recruter à Paris — c'est ici qu'on
    l'attrape."""
    if offre.get("exclue") or offre.get("hors_zone"):
        return
    info = fetcher.info(offre["url"], ttl_j=config.CACHE_TTL_OFFRES_J)
    if info.get("status") in (404, 410):  # lien mort : inutile de candidater
        offre["exclue"] = True
        return
    html = info.get("text")
    if not html:
        return
    t = normaliser(html[:200000])

    if _REGEX_CONTRAT_EXCLU.search(t):
        offre["exclue"] = True
        return

    if lieu_ok(offre.get("lieu", "")) is None:  # lieu encore inconnu
        en_region = (any(v in t for v in config.VILLES)
                     or re.search(r"\b31\d{3}\b", t))
        ville_exclue = _REGEX_VILLES_EXCLUES.search(t)
        if ville_exclue and en_region:
            # la page mentionne Toulouse et une autre ville → l'autre ville
            # prime (ex: « poste à Villefranche, siège à Toulouse »)
            offre["hors_zone"] = True
            offre["lieu"] = ville_exclue.group(0) + " (page de l'offre)"
        elif en_region and not ville_exclue:
            offre["lieu"] = "région toulousaine (page de l'offre)"
        elif ville_exclue:
            offre["hors_zone"] = True
            offre["lieu"] = ville_exclue.group(0) + " (page de l'offre)"
