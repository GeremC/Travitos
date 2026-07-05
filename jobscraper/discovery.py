"""Étape 1 — Découverte des entreprises candidates.

Deux sources :
  - l'annuaire officiel des entreprises (API publique, sans clé) filtré par
    codes NAF et département ;
  - des requêtes DuckDuckGo qui remontent directement des pages carrières.
"""

import logging
import re
import unicodedata
import urllib.parse

import config
from jobscraper.fetch import Fetcher, domaine, domaine_blackliste, racine

log = logging.getLogger("jobscraper.discovery")

API_ANNUAIRE = "https://recherche-entreprises.api.gouv.fr/search"

# formes juridiques à retirer pour dédoublonner les noms
_FORMES = re.compile(r"\b(sasu|sas|sarl|eurl|sa|sci|scop|scic|snc|selarl|gie|"
                     r"association|ste|societe)\b", re.I)


def nom_normalise(nom: str) -> str:
    s = unicodedata.normalize("NFD", nom or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = _FORMES.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _tranches_depuis(minimum: str) -> str:
    t = config.TRANCHES_EFFECTIF
    return ",".join(t[t.index(minimum):])


def entreprises_annuaire(fetcher: Fetcher) -> list[dict]:
    entreprises = []
    for naf, (libelle, tranche_min) in config.NAF_CODES.items():
        n_avant = len(entreprises)
        page = 1
        while page <= 20:
            params = urllib.parse.urlencode({
                "activite_principale": naf,
                "departement": config.DEPARTEMENT,
                "tranche_effectif_salarie": _tranches_depuis(tranche_min),
                "etat_administratif": "A",
                "per_page": 25,
                "page": page,
            })
            data = fetcher.get_json(f"{API_ANNUAIRE}?{params}",
                                    delai=config.DELAI_API_ANNUAIRE_S)
            if not data or not data.get("results"):
                break
            for res in data["results"]:
                # les entrepreneurs individuels ne recrutent pas
                if str(res.get("nature_juridique", "")) == "1000":
                    continue
                # le filtre département matche parfois via un établissement
                # secondaire : on affiche la commune du 31, pas le siège
                siege = res.get("siege") or {}
                etabs = res.get("matching_etablissements") or []
                local = next(
                    (e for e in etabs if str(e.get("code_postal", ""))
                     .startswith(config.DEPARTEMENT)), None) or siege
                entreprises.append({
                    "nom": res.get("nom_complet") or res.get("nom_raison_sociale") or "",
                    "siren": res.get("siren"),
                    "naf": naf,
                    "secteur": libelle,
                    "ville": (local.get("libelle_commune") or "").title(),
                    "cp": local.get("code_postal") or "",
                    "site": None,
                    "page_carrieres": None,
                    "source": "annuaire",
                })
                if len(entreprises) - n_avant >= config.MAX_ENTREPRISES_PAR_NAF:
                    break
            if (len(entreprises) - n_avant >= config.MAX_ENTREPRISES_PAR_NAF
                    or page >= data.get("total_pages", 1)):
                break
            page += 1
        log.info("NAF %s (%s) : %d entreprises", naf, libelle,
                 len(entreprises) - n_avant)
    return entreprises


_LABELS_GENERIQUES = {"www", "fr", "en", "jobs", "careers", "career", "blog",
                      "shop", "m", "app", "recrutement", "emploi"}


def _nom_depuis_domaine(url: str) -> str:
    labels = domaine(url).split(".")
    significatifs = [l for l in labels[:-1] if l not in _LABELS_GENERIQUES]
    label = significatifs[0] if significatifs else labels[0]
    return label.replace("-", " ").title()


def entreprises_recherche(fetcher: Fetcher) -> list[dict]:
    """Les résultats DuckDuckGo sont supposés être des pages carrières ou des
    sites d'entreprises ; on en déduit une entreprise « probable »."""
    entreprises = []
    for requete in config.REQUETES_RECHERCHE:
        resultats = fetcher.recherche(requete, max_resultats=10)
        log.info("Recherche « %s » : %d résultats", requete, len(resultats))
        for r in resultats:
            if domaine_blackliste(r["url"]):
                continue
            entreprises.append({
                "nom": _nom_depuis_domaine(r["url"]),
                "titre_resultat": r["titre"],
                "naf": "",
                "secteur": f"trouvé via « {requete} »",
                "ville": "",
                "cp": "",
                "site": racine(r["url"]),
                "page_carrieres": None,
                "indice_carrieres": r["url"],
                "source": "recherche",
            })
    return entreprises


def dedoublonner(entreprises: list[dict]) -> list[dict]:
    vues_dom, vues_nom, uniques = set(), set(), []
    for e in entreprises:
        dom = domaine(e["site"]) if e.get("site") else None
        nom = nom_normalise(e["nom"])
        if (dom and dom in vues_dom) or (nom and nom in vues_nom):
            continue
        if dom:
            vues_dom.add(dom)
        if nom:
            vues_nom.add(nom)
        uniques.append(e)
    return uniques


def decouvrir(fetcher: Fetcher, sans_recherche: bool = False) -> list[dict]:
    if sans_recherche:
        log.info("Recherche web désactivée — annuaire uniquement.")
        entreprises = entreprises_annuaire(fetcher)
    else:
        # la source « recherche » d'abord : ses entreprises ont déjà un site,
        # et souvent directement une page carrières
        entreprises = entreprises_recherche(fetcher) + entreprises_annuaire(fetcher)
    uniques = dedoublonner(entreprises)
    log.info("Découverte : %d entreprises uniques (%d avant dédoublonnage)",
             len(uniques), len(entreprises))
    return uniques
