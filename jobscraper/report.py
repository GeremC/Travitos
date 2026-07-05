"""Étape 6 — Sorties : resultats.csv, entreprises.csv et rapport.html,
plus la mémoire des offres déjà vues lors des scans précédents."""

import csv
import datetime
import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path

COLONNES_OFFRES = ["entreprise", "titre", "lien_offre", "lieu",
                   "page_carrieres", "score", "score_linguistique",
                   "sur_indeed", "exclue", "hors_zone", "liste_offres",
                   "date_scan"]

_MOTS_CLE = (r"offres?|emplois?|jobs?|carrieres?|careers?|recrutements?|"
             r"postes?|positions?|annonces?|vacanc\w*|openings?|opportunit\w*")
_PREFIXES = (r"nos|toutes|les|mes|vos|leurs?|des|aux|"
             r"nouvelles?|dernieres?|nouveaux?|[0-9]+")

# L'URL se termine par un mot-clé de liste
_MOTIF_FIN = re.compile(
    r"/(" + _MOTS_CLE + r"|"
    r"offres?[-\s]emploi|offres?[-\s]d.emploi)"
    r"[/#]?$", re.I)

# Dernier segment = préfixe? + mot-clé de liste
_MOTIF_DERNIER = re.compile(
    r"^(?:(?:" + _PREFIXES + r")[-\s])?"
    r"(?:" + _MOTS_CLE + r")"
    r"(?:[-\s](?:emploi|d\.emploi))?"
    r"$", re.I)

# Dernier segment = double préfixe (toutes-nos-offres)
_MOTIF_DOUBLE = re.compile(r"^(toutes[-\s]nos[-\s])?" + _MOTS_CLE + r"$", re.I)


def _est_liste_offres(url: str) -> bool:
    """Une URL qui pointe vers une liste d'offres (pas une fiche de poste)."""
    path = urllib.parse.urlsplit(url).path.rstrip("/")
    if _MOTIF_FIN.search(path):
        return True
    last = path.rsplit("/", 1)[-1]
    if _MOTIF_DERNIER.match(last):
        return True
    if _MOTIF_DOUBLE.match(last):
        return True
    return False


COLONNES_ENTREPRISES = ["nom", "secteur", "naf", "ville", "site",
                        "page_carrieres", "nb_offres_trouvees", "source"]


# ------------------------------------------- mémoire des offres déjà vues
def charger_vues(chemin: Path, ancien_csv: Path | None = None) -> dict:
    """{url de l'offre: date de première vue}. Au premier lancement avec
    mémoire, importe le resultats.csv d'un scan précédent s'il existe :
    ces offres ont déjà été livrées, elles ne doivent pas revenir."""
    if Path(chemin).exists():
        try:
            return json.loads(Path(chemin).read_text())
        except Exception:
            return {}
    vues = {}
    if ancien_csv and Path(ancien_csv).exists():
        with open(ancien_csv, encoding="utf-8-sig") as f:
            for ligne in csv.DictReader(f):
                if ligne.get("lien_offre"):
                    vues[ligne["lien_offre"]] = ligne.get("date_scan", "")
    return vues


def enregistrer_vues(chemin: Path, vues: dict, lignes: list[dict]):
    aujourd_hui = datetime.date.today().isoformat()
    for l in lignes:
        vues.setdefault(l["lien_offre"], aujourd_hui)
    Path(chemin).write_text(json.dumps(vues, ensure_ascii=False, indent=0))


def lignes_offres(offres_par_ent: list[tuple[dict, list[dict]]]) -> list[dict]:
    aujourd_hui = datetime.date.today().isoformat()
    lignes = []
    for ent, offres in offres_par_ent:
        for o in offres:
            lien = o.get("url", "")
            lignes.append({
                "entreprise": ent["nom"],
                "titre": o.get("titre", ""),
                "lien_offre": lien,
                "lieu": o.get("lieu", ""),
                "page_carrieres": ent.get("page_carrieres", ""),
                "score": o.get("score", 0),
                "score_linguistique": o.get("score_linguistique", 0),
                "sur_indeed": "oui" if o.get("sur_indeed") else "non",
                "exclue": "oui" if o.get("exclue") else "non",
                "hors_zone": "oui" if o.get("hors_zone") else "non",
                "liste_offres": "oui" if _est_liste_offres(lien) else "non",
                "date_scan": aujourd_hui,
            })
    lignes.sort(key=lambda l: l["score"], reverse=True)
    return lignes


def ecrire_csv_offres(lignes: list[dict], chemin: Path):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES_OFFRES)
        w.writeheader()
        w.writerows(lignes)


def ecrire_csv_entreprises(entreprises: list[dict], chemin: Path):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES_ENTREPRISES)
        w.writeheader()
        for e in entreprises:
            w.writerow({
                "nom": e["nom"], "secteur": e.get("secteur", ""),
                "naf": e.get("naf", ""), "ville": e.get("ville", ""),
                "site": e.get("site", ""),
                "page_carrieres": e.get("page_carrieres", ""),
                "nb_offres_trouvees": e.get("nb_offres", 0),
                "source": e.get("source", ""),
            })


def _e(s) -> str:
    return html.escape(str(s or ""))


def _id_url(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _rendre_ligne(l: dict, controles: bool = False) -> str:
    badge = ""
    if l["score_linguistique"] > 0:
        badge = ' <span class="ling">linguistique</span>'
    liste_tag = (' <span class="muted">(Liste d\u2019offres)</span>'
                 if l.get("liste_offres") == "oui" else "")
    cellule_action = ""
    if controles:
        cellule_action = (
            f'<td class="col-cb"><input type="checkbox" class="postule-cb"'
            f' title="Marquer comme postul\u00e9"></td>'
            f'<td class="col-trash"><button class="trash-btn" title="Masquer d\u00e9finitivement">'
            f'\u2716</button></td>')
    return (
        f'<tr data-id="{_id_url(l["lien_offre"])}">'
        f'{cellule_action}'
        f'<td class="score">{l["score"]}</td>'
        f'<td class="ent">{_e(l["entreprise"])}</td>'
        f'<td><a href="{_e(l["lien_offre"])}" target="_blank">'
        f'{_e(l["titre"])}</a>{badge}{liste_tag}</td>'
        f'<td class="lieu">{_e(l["lieu"])}</td>'
        f'</tr>')


def _tableau_statique(lignes: list[dict]) -> str:
    tr = "\n".join(_rendre_ligne(l) for l in lignes)
    return ("<table><thead><tr><th>Score</th><th>Entreprise</th><th>Offre</th>"
            "<th>Lieu</th></tr></thead><tbody>\n"
            + tr + "\n</tbody></table>")


_HEADER_CONTROLES = ("<thead><tr>"
                     '<th class="col-cb"></th>'
                     "<th>Score</th><th>Entreprise</th><th>Offre</th>"
                     "<th>Lieu</th>"
                     '<th class="col-trash"></th>'
                     "</tr></thead>")


def ecrire_html(lignes: list[dict], entreprises: list[dict], chemin: Path,
                en_cours: bool = False):
    retenues = [l for l in lignes if l["sur_indeed"] == "non"
                and l["exclue"] == "non" and l["hors_zone"] == "non"
                and l["liste_offres"] == "non"]
    sur_indeed = [l for l in lignes if l["sur_indeed"] == "oui"]
    spontanees = [e for e in entreprises
                  if e.get("page_carrieres") and not e.get("nb_offres")]

    lignes_retenues = "\n".join(_rendre_ligne(l, controles=True)
                                for l in retenues)

    date = datetime.date.today().strftime("%d/%m/%Y")
    doc = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Offres hors Indeed — r\u00e9gion toulousaine</title>
<style>
 * {{ box-sizing: border-box; }}
 body {{ background: #272822; color: #f8f8f2; font-family: "Segoe UI", system-ui, sans-serif;
        margin: 2rem auto; max-width: 1100px; line-height: 1.5; }}
 h1 {{ font-size: 1.5rem; color: #a6e22e; margin-bottom: .3rem; }}
 h2 {{ font-size: 1rem; margin-top: 1.5rem; margin-bottom: .4rem; color: #f92672; }}
 h2 .count {{ color: #75715e; font-weight: 400; font-size: .85rem; }}
 a {{ color: #66d9ef; text-decoration: none; }}
 a:hover {{ text-decoration: underline; }}
 table {{ border-collapse: collapse; width: 100%; font-size: .78rem;
         background: #3e3d32; border-radius: 4px; overflow: hidden; }}
 th, td {{ border: 1px solid #49483e; padding: .2rem .35rem; text-align: left;
          overflow: hidden; text-overflow: ellipsis; }}
 th {{ background: #49483e; color: #f8f8f2; font-weight: 600; font-size: .72rem; }}
 tr:nth-child(even) td {{ background: rgba(255,255,255,.02); }}
 tr:hover td {{ background: rgba(255,255,255,.05); }}
 .score {{ text-align: center; font-weight: 600; color: #e6db74; width: 1.8rem; }}
 .ent {{ max-width: 12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
 .lieu {{ max-width: 10rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
 .ling {{ background: #a6e22e; color: #272822; border-radius: 8px;
          padding: 0 .4em; font-size: .65rem; font-weight: 600; white-space: nowrap; }}
 .muted {{ color: #75715e; font-size: .82rem; }}
 .col-cb {{ width: 1.5rem; text-align: center; }}
 .col-trash {{ width: 1.5rem; text-align: center; }}
 .postule-cb {{ transform: scale(.9); cursor: pointer; vertical-align: middle; }}
 .trash-btn, .restore-btn {{ background: none; border: none; color: #f92672;
          cursor: pointer; font-size: .85rem; padding: 0 .15rem; border-radius: 3px; }}
 .trash-btn:hover, .restore-btn:hover {{ background: #49483e; }}
 .restore-btn {{ color: #a6e22e; }}
 #restore-all-btn {{ background: #49483e; border: none; color: #a6e22e;
          cursor: pointer; font-size: .75rem; padding: .2rem .5rem; border-radius: 3px;
          margin-left: .5rem; }}
 #restore-all-btn:hover {{ background: #5c5b4e; }}
 .section-hidden {{ display: none; }}
 .badge-en-cours {{ background: #e6db74; color: #272822; padding: .2rem .6rem;
          border-radius: 4px; font-weight: 600; font-size: .82rem;
          display: inline-block; margin-bottom: .5rem; }}
 .collapsed {{ display: none; }}
 .toggle-link {{ color: #66d9ef; cursor: pointer; font-size: .82rem; margin-left: .5rem; }}
 .toggle-link:hover {{ text-decoration: underline; }}
</style></head><body>
<h1>Offres d\u2019emploi hors Indeed — r\u00e9gion toulousaine</h1>
{'<p class="badge-en-cours">⏳ Scan en cours — résultats partiels (recharger)</p>' if en_cours else ''}
<p class="muted">Scan du {date} &middot; {len(retenues)} offres &middot;
{len(sur_indeed)} sur Indeed &middot;
{len(entreprises)} entreprises.</p>

<div id="offres-section">
<h2>Offres \u00e0 explorer</h2>
<table id="offres-table">
{_HEADER_CONTROLES}
<tbody>
{lignes_retenues}
</tbody>
</table>
</div>

<div id="postule-section" class="section-hidden">
<h2>D\u00e9j\u00e0 postul\u00e9</h2>
<table id="postule-table">
{_HEADER_CONTROLES}
<tbody></tbody>
</table>
</div>

<div id="corbeille-section" class="section-hidden">
<h2>Corbeille <span id="corbeille-count" class="count"></span>
<button id="restore-all-btn" title="Tout restaurer">\u21ba Restaurer tout</button>
<span id="corbeille-toggle" class="toggle-link">\u25b6 Afficher</span></h2>
<div id="corbeille-content" class="collapsed">
<table id="corbeille-table">
{_HEADER_CONTROLES}
<tbody></tbody>
</table>
</div>
</div>

<h2>Candidatures spontan\u00e9es — entreprises avec page carri\u00e8res mais sans offre d\u00e9tect\u00e9e</h2>
<p class="muted">Le scraper n\u2019a pas trouv\u00e9 d\u2019offre list\u00e9e, mais la page carri\u00e8res existe :
utile pour candidater spontan\u00e9ment.</p>
<ul>
{"".join(f'<li><a href="{_e(e["page_carrieres"])}" target="_blank">{_e(e["nom"])}</a>'
         f' <span class="muted">— {_e(e.get("secteur", ""))} {_e(e.get("ville", ""))}</span></li>'
         for e in spontanees)}
</ul>

<h2>Offres \u00e9cart\u00e9es car pr\u00e9sentes sur Indeed</h2>
{_tableau_statique(sur_indeed) if sur_indeed else '<p class="muted">Aucune.</p>'}

<script>
(function() {{
function getState(id) {{
  return {{
    postule: localStorage.getItem('postule_' + id) === 'true',
    corbeille: localStorage.getItem('corbeille_' + id) === 'true'
  }};
}}
function setPostule(id, val) {{
  if (val) localStorage.setItem('postule_' + id, 'true');
  else localStorage.removeItem('postule_' + id);
}}
function setCorbeille(id, val) {{
  if (val) localStorage.setItem('corbeille_' + id, 'true');
  else localStorage.removeItem('corbeille_' + id);
}}

var offreTbody = document.querySelector('#offres-table tbody');
var postuleTbody = document.querySelector('#postule-table tbody');
var corbeilleTbody = document.querySelector('#corbeille-table tbody');
var postuleSection = document.getElementById('postule-section');
var corbeilleSection = document.getElementById('corbeille-section');
var corbeilleContent = document.getElementById('corbeille-content');
var corbeilleToggle = document.getElementById('corbeille-toggle');
var corbeilleCount = document.getElementById('corbeille-count');

function compter(tbody) {{ return tbody.children.length; }}

function mettreAJourVisibilite() {{
  var np = compter(postuleTbody);
  var nc = compter(corbeilleTbody);
  postuleSection.classList.toggle('section-hidden', np === 0);
  var had = corbeilleSection.classList.contains('section-hidden');
  corbeilleSection.classList.toggle('section-hidden', nc === 0);
  corbeilleCount.textContent = '(' + nc + ')';
  // si la corbeille vient juste d'apparaître, on la laisse repliée
  if (!had && nc > 0) {{
    var open = localStorage.getItem('corbeille_open') === 'true';
    corbeilleContent.classList.toggle('collapsed', !open);
    corbeilleToggle.textContent = open ? '\u25bc Masquer' : '\u25b6 Afficher (' + nc + ')';
  }} else if (nc === 0) {{
    corbeilleContent.classList.add('collapsed');
  }}
}}

function ligneVers(cible, tr) {{
  cible.appendChild(tr);
  mettreAJourVisibilite();
}}

// Toggle corbeille
corbeilleToggle.addEventListener('click', function() {{
  var open = corbeilleContent.classList.toggle('collapsed');
  localStorage.setItem('corbeille_open', String(!open));
  var nc = compter(corbeilleTbody);
  corbeilleToggle.textContent = open ? '\u25b6 Afficher (' + nc + ')' : '\u25bc Masquer';
}});

// Restaurer tout
document.getElementById('restore-all-btn').addEventListener('click', function() {{
  var rows = corbeilleTbody.querySelectorAll('tr');
  Array.prototype.forEach.call(rows, function(tr) {{
    setCorbeille(tr.dataset.id, false);
    var cb = tr.querySelector('.postule-cb');
    if (cb) cb.checked = false;
    ligneVers(offreTbody, tr);
  }});
}});

// Appliquer l'\u00e9tat sauvegard\u00e9 au chargement
var cbChange = function(e) {{
  var tr = e.target.closest('tr');
  var id = tr.dataset.id;
  if (e.target.checked) {{
    setPostule(id, true);
    setCorbeille(id, false);
    ligneVers(postuleTbody, tr);
  }} else {{
    setPostule(id, false);
    ligneVers(offreTbody, tr);
  }}
}};

var rows = offreTbody.querySelectorAll('tr');
Array.prototype.forEach.call(rows, function(tr) {{
  var id = tr.dataset.id;
  var cb = tr.querySelector('.postule-cb');
  if (cb) cb.addEventListener('change', cbChange);
  var state = getState(id);
  if (state.postule) {{
    if (cb) cb.checked = true;
    ligneVers(postuleTbody, tr);
  }} else if (state.corbeille) {{
    ligneVers(corbeilleTbody, tr);
  }}
}});

// Les checkbox dans les lignes d\u00e9j\u00e0 d\u00e9plac\u00e9es
[postuleTbody, corbeilleTbody].forEach(function(tbody) {{
  Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function(tr) {{
    var cb = tr.querySelector('.postule-cb');
    if (cb) cb.addEventListener('change', cbChange);
  }});
}});

// Bouton poubelle
document.addEventListener('click', function(e) {{
  var btn = e.target.closest && e.target.closest('.trash-btn');
  if (btn) {{
    var tr = btn.closest('tr');
    var id = tr.dataset.id;
    setCorbeille(id, true);
    setPostule(id, false);
    var cb = tr.querySelector('.postule-cb');
    if (cb) {{ cb.checked = false; cb.removeEventListener('change', cbChange); }}
    var restoreBtn = document.createElement('button');
    restoreBtn.className = 'restore-btn';
    restoreBtn.title = 'Restaurer';
    restoreBtn.textContent = '\u21ba';
    var td = btn.parentNode;
    td.innerHTML = '';
    td.appendChild(restoreBtn);
    ligneVers(corbeilleTbody, tr);
  }}
  var restore = e.target.closest && e.target.closest('.restore-btn');
  if (restore) {{
    var tr = restore.closest('tr');
    var id = tr.dataset.id;
    setCorbeille(id, false);
    var cb = tr.querySelector('.postule-cb');
    if (cb) {{ cb.addEventListener('change', cbChange); }}
    var td = restore.parentNode;
    var trashBtn = document.createElement('button');
    trashBtn.className = 'trash-btn';
    trashBtn.title = 'Masquer d\u00e9finitivement';
    trashBtn.innerHTML = '\u2716';
    td.innerHTML = '';
    td.appendChild(trashBtn);
    ligneVers(offreTbody, tr);
  }}
}});

mettreAJourVisibilite();
}})();
</script>
</body></html>"""
    Path(chemin).write_text(doc, encoding="utf-8")
