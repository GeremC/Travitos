"""Couche réseau : HTTP avec cache disque, rate-limit par domaine,
recherche DuckDuckGo et rendu Playwright en secours pour les pages en JS.
"""

import hashlib
import json
import logging
import random
import re
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger("jobscraper.fetch")

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0"


def domaine(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")


def racine(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def domaine_blackliste(url: str) -> bool:
    dom = domaine(url)
    return any(b in dom for b in config.DOMAINES_BLACKLIST)


class Fetcher:
    def __init__(self, cache_dir: Path, frais: bool = False):
        self.cache_dir = Path(cache_dir) / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._racine_cache = Path(cache_dir)
        self.frais = frais
        self._sites_morts = set()
        if not frais:
            p = self._racine_cache / "sites_morts.json"
            if p.exists():
                self._sites_morts = set(json.loads(p.read_text(encoding="utf-8")))
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
        })
        self._dernier_hit: dict[str, float] = {}
        self._repos_moteur: dict[str, float] = {}
        self._blocs_moteur: dict[str, int] = {}
        self._recherche_abandonnee = False
        self._pw = None  # (playwright, browser, context), lancé paresseusement
        self._stealth_v1 = None

    # ------------------------------------------------------------- cache
    def _chemin(self, cle: str) -> Path:
        return self.cache_dir / (hashlib.sha1(cle.encode()).hexdigest() + ".json")

    def _cache_lire(self, cle: str, ttl_j: float | None = None):
        if self.frais:
            return None
        p = self._chemin(cle)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
        except Exception:
            return None
        if not data.get("ok"):
            ttl_j = config.CACHE_TTL_ECHEC_J
        elif ttl_j is None:
            ttl_j = config.CACHE_TTL_J
        if time.time() - data.get("ts", 0) > ttl_j * 86400:
            return None
        return data

    def _cache_ecrire(self, cle: str, data: dict):
        data["ts"] = time.time()
        try:
            self._chemin(cle).write_text(json.dumps(data, ensure_ascii=False),
                                         encoding="utf-8")
        except Exception as e:
            log.debug("cache non écrit (%s) : %s", cle[:60], e)

    # -------------------------------------------------------- rate limit
    def _attendre(self, url: str, delai: float | None = None):
        netloc = urllib.parse.urlsplit(url).netloc
        delai = config.DELAI_PAR_DOMAINE_S if delai is None else delai
        ecoule = time.time() - self._dernier_hit.get(netloc, 0.0)
        if ecoule < delai:
            time.sleep(delai - ecoule + random.uniform(0, 0.4))
        self._dernier_hit[netloc] = time.time()

    # --------------------------------------------------------------- GET
    def info(self, url: str, delai: float | None = None, timeout=20,
             ttl_j: float | None = None) -> dict:
        """GET avec cache ; retourne {text, status, url_finale, ok}."""
        cle = "GET " + url
        cache = self._cache_lire(cle, ttl_j)
        if cache is not None:
            return cache
        self._attendre(url, delai)
        try:
            r = self.session.get(url, timeout=timeout, allow_redirects=True)
            data = {"text": r.text if r.ok else None, "status": r.status_code,
                    "url_finale": r.url, "ok": r.ok}
        except requests.RequestException as e:
            if "NameResolutionError" not in str(e) and "Failed to resolve" not in str(e):
                log.debug("GET %s : %s", url, e)
            data = {"text": None, "status": None, "url_finale": url,
                    "ok": False, "erreur": str(e)}
        self._cache_ecrire(cle, data)
        return data

    def get(self, url: str, **kw) -> str | None:
        return self.info(url, **kw).get("text")

    def get_json(self, url: str, **kw):
        text = self.get(url, **kw)
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    # --------------------------------------------------------- Playwright
    def _nouvelle_page(self):
        if self._pw is None:
            import os, sys
            orig = os.dup(sys.stderr.fileno())
            null_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(null_fd, sys.stderr.fileno())
            try:
                from playwright.sync_api import sync_playwright
                p = sync_playwright().start()
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=UA, locale="fr-FR")
                try:
                    from playwright_stealth import Stealth
                    Stealth().apply_stealth_sync(ctx)
                except Exception:
                    try:
                        from playwright_stealth import stealth_sync
                        self._stealth_v1 = stealth_sync
                    except Exception:
                        pass
                self._pw = (p, browser, ctx)
            except Exception as e:
                log.debug("Playwright indisponible : %s", e)
                self._pw = "error"
                return None
            finally:
                os.dup2(orig, sys.stderr.fileno())
                os.close(null_fd)
                os.close(orig)
        if self._pw == "error":
            return None
        page = self._pw[2].new_page()
        if self._stealth_v1:
            try:
                self._stealth_v1(page)
            except Exception:
                pass
        return page

    def render(self, url: str, attente_ms: int = 3500,
               ttl_j: float | None = None) -> str | None:
        """Charge la page dans Chromium headless (pour les pages 100 % JS)."""
        cle = "RENDER " + url
        cache = self._cache_lire(cle, ttl_j)
        if cache is not None:
            return cache.get("text")
        self._attendre(url)
        html, page = None, None
        try:
            page = self._nouvelle_page()
            if page is None:
                return None
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(attente_ms)
            html = page.content()
        except Exception as e:
            log.debug("render %s : %s", url, e)
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
        self._cache_ecrire(cle, {"text": html, "ok": html is not None})
        return html

    # -------------------------------------------------------- sites morts
    def site_est_mort(self, nom_normalise: str) -> bool:
        return nom_normalise in self._sites_morts

    def marquer_site_mort(self, nom_normalise: str):
        self._sites_morts.add(nom_normalise)
        p = self._racine_cache / "sites_morts.json"
        p.write_text(json.dumps(sorted(self._sites_morts), ensure_ascii=False),
                     encoding="utf-8")

    def fermer(self):
        if self._pw and self._pw != "error":
            p, browser, ctx = self._pw
            for fn in (ctx.close, browser.close, p.stop):
                try:
                    fn()
                except Exception:
                    pass
            self._pw = None

    # ------------------------------------------------ moteurs de recherche
    # Chaque moteur retourne une liste (éventuellement vide) ou None s'il
    # est bloqué. Un moteur bloqué est mis au repos (cooldown) et on passe
    # au suivant ; si tous sont bloqués, on fait une pause et on réessaie.
    # Seuls les succès sont mis en cache : une relance retente les trous.

    def recherche(self, requete: str, max_resultats: int = 8) -> list[dict]:
        """Recherche web -> [{titre, url}]."""
        if self._recherche_abandonnee:
            return []

        def _filtrer(res):
            return [r for r in res if r["url"].startswith("http")
                    and "duckduckgo.com" not in domaine(r["url"])
                    and "bing.com" not in domaine(r["url"])]

        cle = "SEARCH " + requete
        cache = self._cache_lire(cle)
        if cache is not None:
            return _filtrer(cache.get("resultats", []))[:max_resultats]

        moteurs = [("ddg-html", self._ddg_html),
                   ("ddg-lite", self._ddg_lite),
                   ("bing-navigateur", self._bing_render),
                   ("ddg-navigateur", self._ddg_render)]
        for tour in range(config.RECHERCHE_TOURS):
            aucun_tente = True
            for nom, fn in moteurs:
                if time.time() < self._repos_moteur.get(nom, 0):
                    continue
                aucun_tente = False
                if nom.endswith("navigateur"):
                    log.info("recherche via %s : « %s »", nom, requete[:70])
                resultats = fn(requete)
                if resultats is None:  # bloqué -> repos exponentiel
                    blocs = self._blocs_moteur.get(nom, 0) + 1
                    self._blocs_moteur[nom] = blocs
                    repos = min(config.RECHERCHE_COOLDOWN_S * 2 ** (blocs - 1),
                                config.RECHERCHE_COOLDOWN_MAX_S)
                    log.warning("moteur %s bloqué (%dx), repos %ds",
                                nom, blocs, repos)
                    self._repos_moteur[nom] = time.time() + repos
                    continue
                self._blocs_moteur[nom] = 0
                resultats = _filtrer(resultats)
                self._cache_ecrire(cle, {"resultats": resultats, "ok": True})
                return resultats[:max_resultats]
            if aucun_tente:
                break  # tous les moteurs en repos, inutile de réessayer
            if tour < config.RECHERCHE_TOURS - 1:
                log.warning("tous les moteurs sont bloqués, pause de %ds…",
                            config.RECHERCHE_PAUSE_S)
                time.sleep(config.RECHERCHE_PAUSE_S)
                self._repos_moteur.clear()
        self._recherche_abandonnee = True
        log.warning("Moteurs de recherche bloqués, bascule sur annuaire uniquement.")
        return []  # non mis en cache : sera retentée à la prochaine relance

    @staticmethod
    def _decoder_lien_ddg(href: str) -> str | None:
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/l/" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
            return qs.get("uddg", [None])[0]
        return href

    def _ddg_html(self, requete: str) -> list[dict] | None:
        self._attendre("https://html.duckduckgo.com/", config.DELAI_RECHERCHE_S)
        try:
            r = self.session.post("https://html.duckduckgo.com/html/",
                                  data={"q": requete, "kl": "fr-fr"},
                                  timeout=config.TIMEOUT_RECHERCHE)
        except requests.RequestException as e:
            log.debug("ddg html %s : %s", requete, e)
            return None
        if r.status_code != 200 or "anomaly" in r.text.lower():
            log.warning("DuckDuckGo (html) bloque la requête « %s » (HTTP %s)",
                        requete, r.status_code)
            return None
        soup = BeautifulSoup(r.text, "lxml")
        out = []
        for a in soup.select("a.result__a"):
            url = self._decoder_lien_ddg(a.get("href", ""))
            if url:
                out.append({"titre": a.get_text(" ", strip=True), "url": url})
        return out

    def _ddg_lite(self, requete: str) -> list[dict] | None:
        self._attendre("https://lite.duckduckgo.com/", config.DELAI_RECHERCHE_S)
        try:
            r = self.session.post("https://lite.duckduckgo.com/lite/",
                                  data={"q": requete, "kl": "fr-fr"},
                                  timeout=config.TIMEOUT_RECHERCHE)
        except requests.RequestException as e:
            log.debug("ddg lite %s : %s", requete, e)
            return None
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        out = []
        for a in soup.select("a.result-link, a[rel=nofollow]"):
            url = self._decoder_lien_ddg(a.get("href", ""))
            if url and url.startswith("http"):
                out.append({"titre": a.get_text(" ", strip=True), "url": url})
        return out or None

    def _rendre_page(self, url: str, attente_ms: int = 4000,
                     delai: float | None = None,
                     selecteur: str | None = None) -> str | None:
        self._attendre(url, config.DELAI_RECHERCHE_S if delai is None else delai)
        html, page = None, None
        try:
            page = self._nouvelle_page()
            if page is None:
                return None
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            if selecteur:  # on n'attend que le temps nécessaire
                try:
                    page.wait_for_selector(selecteur, timeout=attente_ms)
                except Exception:
                    pass
            else:
                page.wait_for_timeout(attente_ms)
            html = page.content()
        except Exception as e:
            log.debug("render %s : %s", url, e)
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
        return html

    def _ddg_render(self, requete: str) -> list[dict] | None:
        html = self._rendre_page(
            "https://duckduckgo.com/?kl=fr-fr&q=" + urllib.parse.quote(requete))
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        out = []
        for a in soup.select('a[data-testid="result-title-a"], article h2 a'):
            href = a.get("href", "")
            if href.startswith("http") and "duckduckgo.com" not in href:
                out.append({"titre": a.get_text(" ", strip=True), "url": href})
        return out or None

    @staticmethod
    def _decoder_lien_bing(href: str) -> str | None:
        """Les résultats Bing passent par bing.com/ck/a?…&u=a1<base64>."""
        if "bing.com/ck/" not in href:
            return href
        import base64
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        u = qs.get("u", [""])[0]
        if u.startswith("a1"):
            u = u[2:]
        try:
            return base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode()
        except Exception:
            return None

    def _bing_render(self, requete: str) -> list[dict] | None:
        html = self._rendre_page(
            "https://www.bing.com/search?setlang=fr&cc=fr&q="
            + urllib.parse.quote(requete),
            attente_ms=8000, delai=config.DELAI_BING_S, selecteur="#b_results")
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        if soup.select_one("#b_results") is None:
            return None  # pas de conteneur de résultats : page challenge
        out = []
        for a in soup.select("li.b_algo h2 a"):
            url = self._decoder_lien_bing(a.get("href", ""))
            if url and url.startswith("http"):
                out.append({"titre": a.get_text(" ", strip=True), "url": url})
        return out  # conteneur présent mais vide = vraiment 0 résultat
