#!/usr/bin/env python3
"""Transforme le brouillon du résumé écrit par Claude en édition publiée.

Entrée  : data/brouillon.json (écrit par la routine du matin)
Sorties : data/resume.json (lu par l'appli), data/archives/AAAA-MM-JJ.json,
          data/archives/index.json (liste des éditions)

Dans le brouillon, chaque article est désigné par un morceau de son titre tel
qu'il apparaît dans data/depeches.json : le script retrouve le lien exact, la
source et l'heure. Ainsi aucun lien n'est inventé.

Usage : python3 scripts/publier.py
"""
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
ARCH = DATA / "archives"
GARDER = 60  # nombre d'éditions conservées dans l'historique


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("’", "'")


def main() -> int:
    brouillon = json.loads((DATA / "brouillon.json").read_text(encoding="utf-8"))
    depeches = json.loads((DATA / "depeches.json").read_text(encoding="utf-8"))
    tous = {}
    for t in depeches["themes"]:
        for s in t["sujets"]:
            tous[s["id"]] = s["articles"]
    a_plat = [a for arts in tous.values() for a in arts]

    erreurs, avertissements = [], []
    for champ in ("date", "themes"):
        if champ not in brouillon:
            erreurs.append(f"champ manquant : {champ}")

    for theme in brouillon.get("themes", []):
        for sujet in theme.get("sujets", []):
            if not sujet.get("resume"):
                erreurs.append(f"{sujet.get('id')}: résumé vide")
            resolus = []
            for ref in sujet.get("articles", []):
                cle = norm(ref)
                trouve = next((a for a in tous.get(sujet["id"], []) if cle in norm(a["titre"])), None)
                trouve = trouve or next((a for a in a_plat if cle in norm(a["titre"])), None)
                if trouve:
                    resolus.append({k: trouve[k] for k in ("titre", "source", "url", "date", "origine")})
                else:
                    avertissements.append(f"{sujet['id']}: article introuvable « {ref} »")
            sujet["articles"] = resolus

    for a in avertissements:
        print("[avertissement]", a, file=sys.stderr)
    if erreurs:
        for e in erreurs:
            print("[erreur]", e, file=sys.stderr)
        return 1

    brouillon["genere_le"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    texte = json.dumps(brouillon, ensure_ascii=False, indent=1)
    (DATA / "resume.json").write_text(texte, encoding="utf-8")
    ARCH.mkdir(parents=True, exist_ok=True)
    (ARCH / f"{brouillon['date']}.json").write_text(texte, encoding="utf-8")

    editions = sorted((p.stem for p in ARCH.glob("????-??-??.json")), reverse=True)
    for vieux in editions[GARDER:]:
        (ARCH / f"{vieux}.json").unlink()
    (ARCH / "index.json").write_text(json.dumps(editions[:GARDER]), encoding="utf-8")
    (DATA / "brouillon.json").unlink()
    n = sum(len(s["articles"]) for t in brouillon["themes"] for s in t["sujets"])
    print(f"Édition du {brouillon['date']} publiée : {n} articles liés, {len(avertissements)} introuvables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
