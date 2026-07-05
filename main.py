#!/usr/bin/env python3
"""Scraper d'offres d'emploi « hors Indeed » — région toulousaine.

Pipeline :
  1. découverte des entreprises (annuaire officiel + moteur de recherche)
  2. site officiel de chaque entreprise
  3. page carrières / ATS
  4. extraction des liens d'offres
  5. scoring (linguistique prioritaire) + vérification Indeed
  6. sortie/resultats.csv, sortie/entreprises.csv, sortie/rapport.html

Tout le réseau est mis en cache dans cache/ : une relance reprend là où le
scan s'était arrêté. Exemple :

    python main.py --max-entreprises 20 --sans-indeed-check   # essai rapide
    python main.py                                            # scan complet (long)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import config
from jobscraper import careers, discovery, indeed, jobs, report, scoring
from jobscraper.fetch import Fetcher

RACINE = Path(__file__).parent
CACHE = RACINE / "cache"
SORTIE = RACINE / "sortie"

ETAPE_DECOUVERTE = CACHE / "etapes" / "2_entreprises_enrichies.json"


def sauvegarder_etape(nom: str, donnees):
    etapes = CACHE / "etapes"
    etapes.mkdir(parents=True, exist_ok=True)
    (etapes / f"{nom}.json").write_text(
        json.dumps(donnees, ensure_ascii=False, indent=1))


def demander_mode():
    """Demande à l'utilisateur s'il veut tout regénérer ou réutiliser le cache."""
    if not ETAPE_DECOUVERTE.exists():
        return "complet"
    print()
    print("=" * 62)
    print("  Découverte des entreprises déjà effectuée en cache.")
    print("  Ce n'est pas nécessaire de la relancer à chaque fois :")
    print("  réutiliser le cache suffit pour ré-évaluer les offres")
    print("  avec des critères modifiés.")
    print("=" * 62)
    print()
    print("  1 — Non, réutiliser les entreprises déjà trouvées (rapide)")
    print("  2 — Oui, tout regénérer (lent, trouve de nouvelles entreprises)")
    print()
    while True:
        choix = input("  Votre choix [1/2] : ").strip()
        if choix == "1":
            return "reprise"
        if choix == "2":
            return "complet"
        print("   -> Réponse invalide. Tapez 1 ou 2.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-entreprises", type=int, default=None,
                    help="limite le nombre d'entreprises analysées (essais)")
    ap.add_argument("--sans-indeed-check", action="store_true",
                    help="saute la vérification « présent sur Indeed »")
    ap.add_argument("--frais", action="store_true",
                    help="ignore le cache et re-télécharge tout")
    ap.add_argument("--mode", choices=["complet", "reprise"], default=None,
                    help="force le mode sans demande interactive (pour GUI)")
    ap.add_argument("--naf", nargs="*", default=None,
                    help="limite l'annuaire à ces codes NAF (ex: 74.30Z)")
    ap.add_argument("-v", "--verbeux", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbeux else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("jobscraper")

    if args.naf:
        config.NAF_CODES = {k: v for k, v in config.NAF_CODES.items()
                            if k in args.naf}

    SORTIE.mkdir(exist_ok=True)
    if args.mode:
        mode = args.mode
    else:
        mode = demander_mode() if not args.frais else "complet"
    fetcher = Fetcher(CACHE, frais=args.frais)

    def ecrire_sorties(offres_par_ent, entreprises, en_cours):
        """(Ré)écrit CSV + HTML ; appelé pendant et à la fin du scan."""
        lignes = report.lignes_offres(offres_par_ent)
        report.ecrire_csv_offres(lignes, SORTIE / "resultats.csv")
        report.ecrire_csv_entreprises(entreprises, SORTIE / "entreprises.csv")
        report.ecrire_html(lignes, entreprises, SORTIE / "rapport.html",
                           en_cours=en_cours)

    try:
        if mode == "complet":
            # ---------------------------------------------- 1. découverte
            print("[1/6] Découverte des entreprises…", flush=True)
            entreprises = discovery.decouvrir(fetcher)
            if args.max_entreprises:
                entreprises = entreprises[:args.max_entreprises]
            print(f"      {len(entreprises)} entreprises à analyser.")
            sauvegarder_etape("1_entreprises", entreprises)

            # ------------------------------------- 2-3. sites et carrières
            print("[2-3/6] Sites officiels et pages carrières…", flush=True)
            for i, ent in enumerate(entreprises, 1):
                try:
                    careers.trouver_site(fetcher, ent)
                    careers.trouver_page_carrieres(fetcher, ent)
                    if (ent.get("source") == "recherche" and ent.get("site")
                            and not careers.confirme_region(fetcher, ent)):
                        ent["hors_zone"] = True
                        ent["page_carrieres"] = None
                except Exception as e:
                    log.warning("%s : %s", ent["nom"], e)
                etat = ("hors zone" if ent.get("hors_zone") else
                        "carrières ✓" if ent.get("page_carrieres") else
                        "site ✓" if ent.get("site") else "introuvable")
                print(f"      [{i}/{len(entreprises)}] {ent['nom'][:55]:55s} {etat}",
                      flush=True)
                if i % 10 == 0:
                    report.ecrire_csv_entreprises(entreprises,
                                                  SORTIE / "entreprises.csv")
            sauvegarder_etape("2_entreprises_enrichies", entreprises)
        else:
            # ----------- reprise depuis le cache (rapide)
            print("[1-3/6] Chargement des entreprises depuis le cache…",
                  flush=True)
            if ETAPE_DECOUVERTE.exists():
                entreprises = json.loads(ETAPE_DECOUVERTE.read_text())
                print(f"      {len(entreprises)} entreprises chargées.")
            else:
                log.warning("Cache introuvable, bascule en mode complet.")
                mode = "complet"
                entreprises = discovery.decouvrir(fetcher)
                if args.max_entreprises:
                    entreprises = entreprises[:args.max_entreprises]
                print(f"      {len(entreprises)} entreprises à analyser.")
                sauvegarder_etape("1_entreprises", entreprises)
                for i, ent in enumerate(entreprises, 1):
                    try:
                        careers.trouver_site(fetcher, ent)
                        careers.trouver_page_carrieres(fetcher, ent)
                        if (ent.get("source") == "recherche" and ent.get("site")
                                and not careers.confirme_region(fetcher, ent)):
                            ent["hors_zone"] = True
                            ent["page_carrieres"] = None
                    except Exception as e:
                        log.warning("%s : %s", ent["nom"], e)
                    etat = ("hors zone" if ent.get("hors_zone") else
                            "carrières ✓" if ent.get("page_carrieres") else
                            "site ✓" if ent.get("site") else "introuvable")
                    print(f"      [{i}/{len(entreprises)}] {ent['nom'][:55]:55s} {etat}",
                          flush=True)
                    if i % 10 == 0:
                        report.ecrire_csv_entreprises(entreprises,
                                                      SORTIE / "entreprises.csv")
                sauvegarder_etape("2_entreprises_enrichies", entreprises)

        avec_carrieres = [e for e in entreprises if e.get("page_carrieres")]
        print(f"      {len(avec_carrieres)} pages carrières trouvées.")

        # ------------------------------------------------- 4. offres
        print("[4/6] Extraction des offres…", flush=True)
        offres_par_ent = []
        for i, ent in enumerate(avec_carrieres, 1):
            try:
                offres_ent = jobs.extraire_offres(fetcher, ent)
            except Exception as e:
                log.warning("%s : %s", ent["nom"], e)
                offres_ent = []
            ent["nb_offres"] = len(offres_ent)
            if offres_ent:
                for o in offres_ent:
                    scoring.evaluer(o, ent)
                    # la page de l'offre dit le lieu réel et le vrai contrat
                    try:
                        scoring.verifier_page_offre(fetcher, o)
                    except Exception as e:
                        log.debug("vérif page %s : %s", o.get("url"), e)
                offres_par_ent.append((ent, offres_ent))
                # sorties mises à jour en continu : consultables pendant le scan
                ecrire_sorties(offres_par_ent, entreprises, en_cours=True)
            print(f"      [{i}/{len(avec_carrieres)}] {ent['nom'][:55]:55s} "
                  f"{len(offres_ent)} offre(s)", flush=True)
        total = sum(len(o) for _, o in offres_par_ent)
        print(f"      {total} offres trouvées.")

        # -------------------------------------- 5. vérification Indeed
        # (le scoring est fait au fil de l'étape 4)
        print("[5/6] Vérification Indeed…", flush=True)
        if not args.sans_indeed_check:
            a_verifier = sorted(
                ((ent, o) for ent, offres_ent in offres_par_ent
                 for o in offres_ent
                 if not o["exclue"] and not o["hors_zone"]),
                key=lambda c: c[1]["score"], reverse=True,
            )[:config.MAX_VERIF_INDEED]
            for i, (ent, o) in enumerate(a_verifier, 1):
                try:
                    o["sur_indeed"] = indeed.sur_indeed(fetcher, ent, o)
                except Exception as e:
                    log.warning("check Indeed %s : %s", o.get("titre"), e)
                if i % 10 == 0 or i == len(a_verifier):
                    print(f"      vérification Indeed {i}/{len(a_verifier)}",
                          flush=True)
                    ecrire_sorties(offres_par_ent, entreprises, en_cours=True)
        sauvegarder_etape("5_offres", [
            {"entreprise": ent["nom"], "offres": offres_ent}
            for ent, offres_ent in offres_par_ent])

        # ------------------------------------------------ 6. sorties
        print("[6/6] Écriture des résultats…", flush=True)
        ecrire_sorties(offres_par_ent, entreprises, en_cours=False)

        toutes_lignes = report.lignes_offres(offres_par_ent)
        retenues = [l for l in toutes_lignes if l["sur_indeed"] == "non"
                    and l["exclue"] == "non" and l["hors_zone"] == "non"
                    and l["liste_offres"] == "non"]
        print(f"""
Terminé.
  Offres retenues : {len(retenues)} (dont {sum(1 for l in retenues if l['score_linguistique'] > 0)} linguistiques)
  Offres écartées (sur Indeed) : {sum(1 for l in toutes_lignes if l['sur_indeed'] == 'oui')}
  Entreprises analysées : {len(entreprises)}
  -> {SORTIE / 'rapport.html'}
  -> {SORTIE / 'resultats.csv'}
  -> {SORTIE / 'entreprises.csv'}""")
    finally:
        fetcher.fermer()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu. Le cache est conservé : relance pour reprendre.",
              file=sys.stderr)
        sys.exit(130)
