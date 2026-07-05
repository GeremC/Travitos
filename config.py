"""Configuration du scraper d'offres « hors Indeed » — région toulousaine.

Tout ce qui est ajustable (mots-clés, secteurs, limites) est ici.
"""

# ---------------------------------------------------------------- géographie
DEPARTEMENT = "31"

# Villes de la région toulousaine acceptées dans la localisation d'une offre.
VILLES = [
    "toulouse", "blagnac", "colomiers", "labege", "balma", "ramonville",
    "tournefeuille", "muret", "cugnaux", "portet", "saint-orens", "st-orens",
    "l'union", "castanet", "escalquens", "plaisance-du-touch", "cornebarrieu",
    "aucamville", "launaguet", "basso cambo", "montaudran", "purpan",
    "haute-garonne", "occitanie",
]
# Une offre en télétravail complet est aussi acceptable.
MOTIFS_REMOTE = r"teletravail|remote|a distance|home office"

# Villes qui excluent une offre si elles apparaissent comme lieu du poste :
# une entreprise basée à Toulouse peut très bien recruter à Paris.
# (mots entiers, sans accents ; « nice » et « tours » omis, trop ambigus)
VILLES_EXCLUES = [
    "paris", "lyon", "marseille", "montpellier", "bordeaux", "nantes",
    "lille", "strasbourg", "rennes", "grenoble", "sophia antipolis",
    "aix-en-provence", "rouen", "dijon", "angers", "reims", "le havre",
    "saint-etienne", "toulon", "nancy", "metz", "clermont-ferrand",
    "orleans", "caen", "limoges", "brest", "nimes", "perpignan", "pau",
    "bayonne", "biarritz", "annecy", "avignon", "poitiers", "besancon",
    "mulhouse", "la defense", "boulogne-billancourt", "levallois",
    "issy-les-moulineaux", "nanterre", "courbevoie", "velizy", "massy",
    "saclay", "ile-de-france",
    "villefranche", "roanne", "valence", "chambery", "annecy", "bourgoin",
    "vienne", "bourges", "troyes", "chartres", "evreux", "lorient",
    "quimper", "la rochelle", "angouleme", "brive", "ajaccio", "bastia",
    "cannes", "antibes", "frejus", "draguignan", "aubagne", "istres",
    "martigues", "salon-de-provence", "arles", "beziers", "carcassonne",
    "albi", "castres", "rodez", "agen", "tarbes", "mont-de-marsan",
    "dax", "pau", "bayonne", "biarritz",
]

# --------------------------------------------------- secteurs (codes NAF)
# code NAF -> (libellé, tranche d'effectif minimale INSEE)
# Tranches INSEE : 00=0 salarié, 01=1-2, 02=3-5, 03=6-9, 11=10-19, 12=20-49,
# 21=50-99, 22=100-199, 31=200-249, 32=250-499, 41=500-999, 42+=1000 et plus.
# Les secteurs proches de la linguistique acceptent de petites structures ;
# les secteurs plus génériques exigent une taille minimale pour limiter le bruit.
NAF_CODES = {
    "74.30Z": ("Traduction et interprétation", "01"),
    "58.11Z": ("Édition de livres", "01"),
    "58.14Z": ("Édition de revues et périodiques", "01"),
    "63.91Z": ("Agences de presse", "01"),
    "72.20Z": ("R&D en sciences humaines et sociales", "02"),
    "70.21Z": ("Conseil en relations publiques et communication", "03"),
    "85.59A": ("Formation continue d'adultes", "11"),
    "85.59B": ("Autres enseignements", "11"),
    "73.11Z": ("Agences de publicité", "11"),
    "58.29C": ("Édition de logiciels applicatifs", "11"),
    "62.01Z": ("Programmation informatique", "12"),
    "62.02A": ("Conseil en systèmes et logiciels informatiques", "12"),
    "82.20Z": ("Activités de centres d'appels", "12"),
    "84.12Z": ("Administration publique générale", "21"),
    "84.13Z": ("Administration publique (tutelle) de la santé, de la formation, de la culture et des services sociaux", "21"),
    "88.99B": ("Action sociale sans hébergement n.c.a.", "11"),
    "78.10Z": ("Activités des agences de placement de main-d'œuvre", "12"),
    "82.11Z": ("Services administratifs combinés de bureau", "12"),
    "85.60Z": ("Activités de soutien à l'enseignement", "12"),
}
TRANCHES_EFFECTIF = ["00", "01", "02", "03", "11", "12", "21", "22",
                     "31", "32", "41", "42", "51", "52", "53"]
MAX_ENTREPRISES_PAR_NAF = 60

# ------------------------------------------------ requêtes moteur de recherche
REQUETES_RECHERCHE = [
    'recrutement linguiste Toulouse',
    'offre emploi traducteur CDI Toulouse',
    'offre emploi "ingénieur linguiste" Toulouse',
    'recrutement "traitement automatique des langues" Toulouse',
    '"nous recrutons" rédacteur Toulouse',
    'careers NLP Toulouse',
    'offre emploi correcteur relecteur Toulouse',
    'agence de traduction Toulouse recrute',
    'recrutement formateur FLE Toulouse',
    'offre emploi terminologue Toulouse',
    'recrutement chargé de communication CDI Toulouse',
    '"rejoignez notre équipe" CDI Toulouse rédaction',
    'offre emploi conseiller clientèle Toulouse',
    'recrutement "conseiller clientèle" Toulouse',
    'recrutement "agent d\'accueil" Toulouse',
    'offre emploi téléconseiller Toulouse',
    'recrutement hôte d\'accueil Toulouse',
    'offre emploi service client Toulouse',
    'recrutement "agent territorial" Toulouse',
    'offre emploi accompagnement social Toulouse',
    'offre emploi médiateur Toulouse',
    'recrutement France Travail Toulouse',
    'recrutement CAF Toulouse',
    'offre emploi relation client Toulouse',
]

# ------------------------------------------------------------------ scoring
# Motifs regex (sur texte normalisé sans accents, en minuscules) -> poids.
MOTS_CLES_LINGUISTIQUE = [
    (r"linguist", 10),
    (r"traduc|translat", 9),
    (r"terminolog|lexicograph", 9),
    (r"\bnlp\b|natural language|traitement automatique (de la|des) langue", 9),
    (r"\btal\b", 8),
    (r"annotation|annotateur", 7),
    (r"interpretariat|interprete\b", 7),
    (r"correcteur|correctrice|relect", 6),
    (r"\bfle\b|francais langue etrangere", 6),
    (r"localisation|localization", 5),
    (r"transcription", 5),
    (r"redacteur|redactrice|redactionnel", 5),
    (r"ux writer|copywrit", 5),
    (r"speech|reconnaissance vocale", 4),
    (r"editorial", 4),
    (r"charge(e)? de communication", 3),
    (r"formateur|formatrice", 3),
    (r"contenu|content manager", 3),
    (r"documentaliste|documentation technique", 3),

    # Métiers du « bien parler » : accueil, social, conseil, relation client…
    # Ces métiers exigent de bonnes compétences linguistiques sans être
    # directement des métiers de la langue.
    (r"conseiller\w*\s+france\s+travail", 2),
    (r"conseiller\w*\s+en\s+insertion", 2),
    (r"conseiller\w*\s+clientel", 2),
    (r"charge\w*\s+de\s+clientel", 2),
    (r"charge\w*\s+d['\u2019]?\s*accueil", 2),
    (r"hote\s+(d['\u2019]?\s*)?accueil", 2),
    (r"teleconseiller|conseiller\s+a\s+distance", 2),
    (r"relation\s+client", 2),
    (r"service\s+client", 1),
    (r"assistant\w*\s+social", 2),
    (r"agent\s+d['\u2019]?\s*accueil", 2),
    (r"agent\s+de\s+mediation", 2),
    (r"agent\s+territorial", 2),
    (r"\baccueil\b", 1),
    (r"secretariat|secretaire\b", 1),
    (r"mediateur|mediation", 2),
    (r"accompagnement\s+social", 2),
    (r"editeur\b|edition\b|editions\b|librarie|libraire", 2),
    (r"bibliothecaire|documentation\b", 2),
]

# Offres écartées d'office (on ne veut que du CDI/CDD temps plein).
MOTIFS_EXCLUSION = (r"stage\b|stagiaire|alternan|apprenti|professionnalisation|"
                    r"freelance|independant|benevol|temps partiel|mi-temps|"
                    r"\binterim\b|saisonnier|job etudiant|\bvacataire\b")
MOTIFS_TEMPS_PLEIN = r"\bcdi\b|temps plein|full[ -]?time|\b3[589]\s?h\b"

# Offres qui ne sont pas de vraies offres (navigation, CTA, pages catégories…)
# Chaque motif est cherché dans le titre normalisé (sans accents, minuscules).
TITRES_PAS_OFFRE = [
    # navigation pages carrières (anglais)
    "our teams", "our culture", "our values", "our benefits",
    "our commitments", "our development", "our recruitment process",
    "our purpose", "our contributions",
    "purpose-driven", "purpose driven",
    "learn more", "view all", "join our talent",
    "read more", "know more", "see all jobs",
    "inclusion & diversity", "inclusion diversity",
    "learning & development", "learning development",
    # navigation CTA / pages génériques
    "take me there", "life at ",
    "nous rejoindre", "nous recrutons",
    "deposez votre candidature", "votre profil", "votre candidature",
    "travailler ici", "developpement de carrieres",
    "conseils de pro", "domaines d'expertise",
    "utilisation de l'ia", "visit akkodis",
    # navigation pages carrières (français)
    "les metiers de", "les metiers du", "les metiers comme",
    "les metiers chez", "les metiers ",
    "les temoignages", "les etapes de recrutement",
    "le processus de recrutement",
    "nos formations", "nos secteurs", "nos metiers",
    "notre mission", "jobs par type",
    "je m'inscris", "protection des donnees",
    "inclusion et diversite", "la vie chez",
    "avantages sociaux", "rechercher des offres",
    "toutes nos offres", "offres d'emploi par",
    "possibilites de carriere",
    # pages catégories AFP
    "transaction habitation", "gestion & location",
    "decouvrir les formations", "mobilite innover",
    # Oracle / grands groupes
    "career development", "military and veterans",
    "people with disabilities", "social impact",
    "work we do", "security clearance",
    "corporate functions", "getting hired",
    "campus recruiting", "apply now about",
    "engineering and development", "development and engineering",
    "implementation consulting",
    # pages génériques rachetées
    "processus de recrutement",
    "candidature spontanee",
    "domaines d'expertise",
    "syndic de copropriete",
    "entreprise et commerce",
    "siege century",
    # icônes Material Design collées dans le texte
    "arrow_circle_right", "arrow_forward",
    # catégories / pages d'index
    "ventes et developpement commercial",
    "index egalite",
    # sélecteurs de langue
    "france (franc",
    "belgique (franc",
    # mots isolés (cherchés avec \b)
    "locations", "benefits", "students", "graduates", "internships",
    "particuliers", "professionnels", "entreprises", "overview",
]

# Titres qui ne sont PAS des offres seulement quand le titre EST exactement
# ce mot (trop dangereux en \b car « Consulting Manager » serait exclu).
TITRES_PAS_OFFRE_EXACTS = [
    "consulting",
    "university",
]

# ------------------------------------------------------- pages carrières
MOTS_CARRIERES = [
    "recrutement", "recrute", "carriere", "carrieres", "nous rejoindre",
    "rejoignez", "rejoins-nous", "jobs", "careers", "career",
    "offres d'emploi", "offre d'emploi", "emplois", "join us", "we're hiring",
    "on recrute", "postuler", "talents",
]
CHEMINS_CARRIERES = [
    "/recrutement", "/carrieres", "/carriere", "/nous-rejoindre",
    "/rejoignez-nous", "/jobs", "/careers", "/offres-emploi", "/emploi",
    "/fr/carrieres", "/fr/recrutement",
]

# Domaines qui ne sont jamais le site d'une entreprise (agrégateurs, annuaires,
# réseaux sociaux…). Comparaison par sous-chaîne sur le nom de domaine.
DOMAINES_BLACKLIST = [
    "indeed.", "linkedin.", "glassdoor.", "hellowork.", "apec.fr", "meteojob.",
    "jobijoba.", "keljob.", "monster.", "regionsjob.", "pole-emploi.",
    "francetravail.", "optioncarriere.", "jooble.", "adzuna.", "talent.com",
    "cadremploi.", "letudiant.", "studentjob.", "jobteaser.", "emploi-store",
    "societe.com", "pappers.", "pagesjaunes.", "annuaire-entreprises.",
    "infogreffe.", "verif.com", "kompass.", "choosemycompany.",
    "wikipedia.", "facebook.", "instagram.", "twitter.", "x.com", "youtube.",
    "tiktok.", "google.", "bing.com", "duckduckgo.", "leboncoin.",
    "trustpilot.", "mappy.", "tripadvisor.", "yelp.", "malt.fr", "fiverr.",
    "upwork.",
    # agrégateurs d'offres supplémentaires
    "jobsora.", "jobrapido.", "mitula.", "trovit.", "jobted.", "whatjobs.",
    "bebee.", "jobeka.", "fr.expertini", "jobtome.", "neuvoo.", "jobzil",
    # agences d'intérim / cabinets : leurs offres sont partout, Indeed compris
    "manpower.", "adecco.", "randstad.", "synergie.", "proman-", "proman.",
    "crit-job", "groupe-crit", "actual.", "hays.", "expectra.",
    "pagepersonnel.", "michaelpage.", "welljob.", "supplay.", "startpeople.",
    "temporis", "jobandtalent.", "leaderintérim", "leader-interim",
]

# ----------------------------------------------------------------- limites
DELAI_PAR_DOMAINE_S = 1.5      # politesse entre deux requêtes sur un même site
DELAI_RECHERCHE_S = 8.0        # les moteurs de recherche bloquent vite : lentement
DELAI_BING_S = 4.0             # Bing (via navigateur) tolère un rythme plus soutenu
RECHERCHE_COOLDOWN_S = 600     # repos d'un moteur après un blocage…
RECHERCHE_COOLDOWN_MAX_S = 3600  # …doublé à chaque blocage consécutif, plafonné
RECHERCHE_PAUSE_S = 90         # pause quand tous les moteurs sont bloqués
RECHERCHE_TOURS = 3            # nombre de tours avant d'abandonner une requête
TIMEOUT_RECHERCHE = (8, 12)    # (connexion, lecture) — un moteur qui ne répond
                               # pas vite est un moteur qui bloque
DELAI_API_ANNUAIRE_S = 0.4
CACHE_TTL_J = 7                # durée de vie du cache disque
CACHE_TTL_ECHEC_J = 1          # les échecs réseau sont retentés plus tôt
CACHE_TTL_OFFRES_J = 0.75      # les pages listant les offres sont rafraîchies
                               # à chaque scan quotidien (18 h)
MAX_OFFRES_PAR_ENTREPRISE = 40
MAX_VERIF_INDEED = 250         # plafond de recherches « site:fr.indeed.com »
