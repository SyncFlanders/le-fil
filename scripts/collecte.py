#!/usr/bin/env python3
"""Collecte les derniers titres de chaque sujet depuis Google Actualités (RSS).

Aucune clé, aucune dépendance : bibliothèque standard Python seulement.
Écrit data/depeches.json, lu par l'appli (onglet « Dépêches ») et par la
routine Claude qui rédige le résumé du matin.

Usage : python3 scripts/collecte.py
"""
import json
import re
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SUJETS = RACINE / "sujets.json"
SORTIE = RACINE / "data" / "depeches.json"

EDITIONS = {
    "fr": "hl=fr&gl=FR&ceid=FR:fr",
    "en": "hl=en-US&gl=US&ceid=US:en",
}
MAX_PRESSE = 25  # titres Google Actualités gardés par sujet
MAX_PASSIONNES = 15  # titres des sites de passionnés gardés par sujet
UA = "Mozilla/5.0 (compatible; LeFil/1.0; lecteur RSS personnel)"
ATOM = "{http://www.w3.org/2005/Atom}"

try:  # certificats de certifi si présents (Python de python.org sur macOS)
    import certifi

    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def cle_doublon(titre: str) -> str:
    mots = [m for m in normaliser(titre).split() if len(m) > 3]
    return " ".join(sorted(mots[:8]))


def telecharger(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return ET.fromstring(r.read())


def lire_date(texte: str | None) -> datetime | None:
    if not texte:
        return None
    texte = texte.strip()
    try:
        return parsedate_to_datetime(texte)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return None


def article(titre, source, url, date, langue, origine) -> dict:
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return {
        "titre": re.sub(r"\s+", " ", titre).strip(),
        "source": source,
        "url": url,
        "date": date.astimezone(timezone.utc).isoformat(timespec="minutes"),
        "langue": langue,
        "origine": origine,  # "presse" (Google Actualités) ou "passionnes"
    }


def lire_google(requete: str, langue: str, fenetre_h: int) -> list[dict]:
    jours = max(1, round(fenetre_h / 24))
    q = f"{requete} when:{jours}d"
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(q)
        + "&"
        + EDITIONS[langue]
    )
    items = []
    for it in telecharger(url).iter("item"):
        titre = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        # Google ajoute « - Source » à la fin du titre : on le retire.
        if source and titre.endswith(" - " + source):
            titre = titre[: -len(source) - 3].strip()
        date = lire_date(it.findtext("pubDate"))
        if date:
            items.append(article(titre, source, (it.findtext("link") or "").strip(), date, langue, "presse"))
    return items


def lire_flux(url: str, langue: str, nom: str | None) -> list[dict]:
    """Flux RSS ou Atom d'un site (blogs de passionnés, presse spécialisée)."""
    racine = telecharger(url)
    nom = nom or urllib.parse.urlparse(url).netloc.removeprefix("www.")
    items = []
    for it in racine.iter("item"):  # RSS
        date = lire_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))
        if date:
            items.append(article(it.findtext("title") or "", nom, (it.findtext("link") or "").strip(), date, langue, "passionnes"))
    for it in racine.iter(ATOM + "entry"):  # Atom
        date = lire_date(it.findtext(ATOM + "published") or it.findtext(ATOM + "updated"))
        lien = it.find(ATOM + "link[@rel='alternate']")
        if lien is None:
            lien = it.find(ATOM + "link")
        url_a = lien.get("href", "") if lien is not None else ""
        if date:
            items.append(article(it.findtext(ATOM + "title") or "", nom, url_a, date, langue, "passionnes"))
    return items


def main() -> int:
    conf = json.loads(SUJETS.read_text(encoding="utf-8"))
    # Une exclusion trop courte ou faite de chiffres (« 20 ») effacerait des titres sans rapport : on l'ignore.
    exclusions = [e for e in (normaliser(x) for x in conf.get("exclusions_globales", [])) if len(e) >= 4 and not e.isdigit()]
    sources_exclues = [normaliser(x) for x in conf.get("sources_exclues", [])]
    maintenant = datetime.now(timezone.utc)
    sortie = {"genere_le": maintenant.isoformat(timespec="minutes"), "themes": []}
    erreurs = 0

    for theme in conf["themes"]:
        t_out = {"id": theme["id"], "titre": theme["titre"], "sujets": []}
        for sujet in theme["sujets"]:
            fenetre = sujet.get("fenetre_h", 24)
            limite = maintenant - timedelta(hours=fenetre)
            vus, articles = set(), []
            # Les sources de comptes rendus de match passent en premier (le dédoublonnage garde leur version)
            sources = sorted(sujet["requetes"], key=lambda r: not r.get("compte_rendu")) + sujet.get("flux", [])
            for rq in sources:
                try:
                    if "q" in rq:
                        items = lire_google(rq["q"], rq.get("langue", "fr"), rq.get("fenetre_h", fenetre))
                    else:
                        items = lire_flux(rq["flux"], rq.get("langue", "en"), rq.get("nom"))
                except Exception as e:  # un flux en panne ne bloque pas les autres
                    erreurs += 1
                    print(f"[erreur] {sujet['id']} / {rq.get('q') or rq.get('flux')}: {e}", file=sys.stderr)
                    continue
                filtre = [normaliser(m) for m in rq.get("filtre", [])]
                for a in items:
                    if filtre and not any(f in normaliser(a["titre"]) for f in filtre):
                        continue
                    if datetime.fromisoformat(a["date"]) < maintenant - timedelta(hours=rq.get("fenetre_h", fenetre)):
                        continue
                    t = normaliser(a["titre"])
                    if any(x and x in t for x in exclusions):
                        continue
                    if any(x and x in normaliser(a["source"]) for x in sources_exclues):
                        continue
                    cle = cle_doublon(a["titre"])
                    if cle in vus:
                        continue
                    vus.add(cle)
                    if rq.get("compte_rendu"):
                        a = dict(a, origine="passionnes", compte_rendu=True)
                    articles.append(a)
                time.sleep(0.5)  # politesse envers Google
            articles.sort(key=lambda a: a["date"], reverse=True)
            t_out["sujets"].append(
                {
                    "id": sujet["id"],
                    "titre": sujet["titre"],
                    "articles": sorted(
                        [a for a in articles if a["origine"] == "presse"][:MAX_PRESSE]
                        + [a for a in articles if a["origine"] == "passionnes" and not a.get("compte_rendu")][:MAX_PASSIONNES]
                        + [a for a in articles if a.get("compte_rendu")][:12],
                        key=lambda a: a["date"],
                        reverse=True,
                    ),
                }
            )
            print(f"{sujet['id']:<16} {len(articles):>3} articles")
        sortie["themes"].append(t_out)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {SORTIE.relative_to(RACINE)} ({erreurs} flux en erreur)")
    # Échec seulement si tout est tombé : sinon on publie ce qu'on a.
    total = sum(len(s["articles"]) for t in sortie["themes"] for s in t["sujets"])
    return 1 if total == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
