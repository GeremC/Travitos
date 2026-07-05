# Scraper d'offres d'emploi « hors Indeed » — région toulousaine

Trouve les offres publiées **directement sur les sites des entreprises**
(le « marché caché »), avec priorité aux postes liés à la linguistique,
et écarte celles qui apparaissent aussi sur Indeed.

## Utilisation

```bash
# scan complet (long : plusieurs heures, c'est normal — délais de politesse)
python3 main.py

# essai rapide
python3 main.py --max-entreprises 20 --sans-indeed-check

# seulement certains secteurs
python3 main.py --naf 74.30Z 58.11Z
```

Le scan peut être interrompu (Ctrl-C) et relancé : tout le réseau est mis en
cache dans `cache/` (7 jours), la relance reprend quasi instantanément là où
elle s'était arrêtée.

## Lancement quotidien

Le scraper a une **mémoire inter-scans** (`cache/offres_vues.json`) : chaque
offre n'est livrée qu'une fois. Au lancement du lendemain, `resultats.csv` et
`rapport.html` ne contiennent que les **nouvelles** offres du jour ; les pages
d'offres sont re-téléchargées à chaque scan quotidien (TTL de 18 h), le reste
(sites, pages carrières) reste en cache 7 jours donc les scans suivants sont
bien plus rapides que le premier.

```bash
python3 main.py          # scan du jour : uniquement les nouveautés
python3 main.py --tout   # ré-affiche aussi les offres déjà vues
```

## Résultats (dossier `sortie/`)

| Fichier | Contenu |
|---|---|
| `rapport.html` | offres triées par pertinence, liens cliquables, + entreprises pour candidatures spontanées |
| `resultats.csv` | toutes les offres (entreprise, titre, lien, score, sur_indeed…) |
| `entreprises.csv` | toutes les entreprises probables (nom, secteur, ville, site, page carrières) |

## Comment ça marche

1. **Découverte** — entreprises de Haute-Garonne par secteur via l'annuaire
   officiel (API publique) + pages carrières trouvées par moteur de recherche
   (DuckDuckGo puis Bing, avec rotation automatique quand un moteur bloque).
2. **Site & page carrières** — devinette de domaine (`nom-entreprise.fr/.com/.eu`),
   sinon moteur de recherche avec validation (le site doit mentionner le nom de
   l'entreprise) ; détection du lien « recrutement / carrières / nous rejoindre »
   et des plateformes de recrutement (Welcome to the Jungle, Recruitee,
   Greenhouse, Lever…).
3. **Offres** — API JSON de la plateforme quand elle existe, sinon parsing
   HTML, sinon rendu navigateur (Playwright) pour les pages en JavaScript.
4. **Filtres** — score linguistique (traduction, TAL/NLP, rédaction…),
   temps plein (stage/alternance/temps partiel écartés), localisation
   toulousaine, puis vérification `site:fr.indeed.com` : les offres présentes
   sur Indeed sont marquées et écartées du rapport.

## Réglages

Tout est dans [config.py](config.py) : mots-clés et leurs poids, codes NAF,
villes acceptées, requêtes de recherche, délais, plafonds.

## Dépendances

```bash
pip install -r requirements.txt
playwright install chromium   # si Chromium n'est pas déjà installé
```
