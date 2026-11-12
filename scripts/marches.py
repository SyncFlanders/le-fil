#!/usr/bin/env python3
"""Cours du jour pour le thème Marchés : indices, taux, matières premières, devises et cryptos.

Sources gratuites, sans clé :
- Yahoo Finance (API de graphiques, publique mais non officielle ; cours différés d'environ 15 min) ;
- CoinGecko (API publique gratuite) pour les cryptos.
Écrit data/marches.json. Usage : python3 scripts/marches.py
"""
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "marches.json"
UA = "Mozilla/5.0 (compatible; LeFil/1.0; https://github.com/SyncFlanders/le-fil)"
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

# (sujet, symbole Yahoo, nom affiché, unité)
INDICES = [
    ("bourse", "^FCHI", "CAC 40", "pts"),
    ("bourse", "^STOXX50E", "Euro Stoxx 50", "pts"),
    ("bourse", "^GSPC", "S&P 500", "pts"),
    ("bourse", "^IXIC", "Nasdaq", "pts"),
    ("bourse", "^TNX", "Taux US 10 ans", "%"),
    ("bourse", "EURUSD=X", "Euro / dollar", "$"),
    ("bourse", "BZ=F", "Pétrole Brent", "$"),
    ("bourse", "GC=F", "Or (once)", "$"),
]
CRYPTOS = [("bitcoin", "Bitcoin"), ("ethereum", "Ethereum"), ("solana", "Solana")]


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return json.loads(r.read())


def main() -> int:
    ancien = json.loads(SORTIE.read_text(encoding="utf-8")) if SORTIE.exists() else {}
    anciens = {c["id"]: c for c in ancien.get("cours", [])}
    cours, erreurs = [], 0
    for sujet, sym, nom, unite in INDICES:
        try:
            d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d")
            res = d["chart"]["result"][0]
            prix = res["meta"]["regularMarketPrice"]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            prec = closes[-2] if len(closes) >= 2 else res["meta"].get("chartPreviousClose")
            c = {"id": sym, "sujet": sujet, "nom": nom, "valeur": prix, "unite": unite,
                 "variation": round((prix / prec - 1) * 100, 2) if prec else None,
                 "maj": datetime.fromtimestamp(res["meta"]["regularMarketTime"], timezone.utc).isoformat(timespec="minutes")}
            if unite == "%" and prec:
                # Pour un taux, la variation se lit en points de base, pas en pourcentage du taux
                c["variation_pb"] = round((prix - prec) * 100)
            cours.append(c)
        except Exception as ex:
            erreurs += 1
            print(f"[erreur] {nom}: {ex}", file=sys.stderr)
            if sym in anciens:
                cours.append(anciens[sym])
    try:
        ids = ",".join(i for i, _ in CRYPTOS)
        d = get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur&include_24hr_change=true&include_last_updated_at=true")
        for i, nom in CRYPTOS:
            x = d[i]
            cours.append({"id": i, "sujet": "crypto", "nom": nom, "valeur": x["eur"], "unite": "€",
                          "variation": round(x.get("eur_24h_change") or 0, 2), "sur": "24 h",
                          "maj": datetime.fromtimestamp(x["last_updated_at"], timezone.utc).isoformat(timespec="minutes")})
    except Exception as ex:
        erreurs += 1
        print(f"[erreur] cryptos: {ex}", file=sys.stderr)
        cours += [c for c in anciens.values() if c["sujet"] == "crypto"]
    SORTIE.write_text(json.dumps({"genere_le": datetime.now(timezone.utc).isoformat(timespec="minutes"), "cours": cours}, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in cours:
        print(f"{c['nom']:<16} {c['valeur']:>12} {c['unite']:<3} {c['variation']:+.2f} % {c.get('variation_pb', '')}")
    print(f"→ data/marches.json ({erreurs} erreurs)")
    return 0 if cours else 1


if __name__ == "__main__":
    sys.exit(main())
