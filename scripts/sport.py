#!/usr/bin/env python3
"""Calendrier, derniers résultats et photos des joueurs des équipes suivies.

Sources gratuites, sans clé :
- ESPN (site.api.espn.com, API publique non officielle) : matchs, effectifs, photos
  des joueurs NFL, NBA et football universitaire ;
- Wikipédia (API REST) : photos libres de droits quand ESPN n'en a pas (football européen).

Écrit data/sport.json, lu par l'appli et par scripts/publier.py.
Usage : python3 scripts/sport.py
"""
import json
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SUJETS = RACINE / "sujets.json"
SORTIE = RACINE / "data" / "sport.json"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
UA = "LeFil/1.0 (https://github.com/SyncFlanders/le-fil; lecteur personnel)"
# Mots qui doivent figurer dans la description Wikipédia, pour ne pas prendre un homonyme.
MOTS_WIKI = {
    "soccer": ["footballer", "football player", "soccer"],
    "football": ["american football"],
    "basketball": ["basketball"],
}

try:
    import certifi

    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def cle(nom: str) -> str:
    t = unicodedata.normalize("NFKD", nom.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).replace(".", " ").split())


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return json.loads(r.read())


def score(c: dict) -> str | None:
    s = c.get("score")
    if isinstance(s, dict):
        s = s.get("displayValue") or s.get("value")
    return None if s in (None, "") else str(s).removesuffix(".0")


def match(ev: dict, id_equipe: str) -> dict:
    comp = ev["competitions"][0]
    nous = next((c for c in comp["competitors"] if str(c["team"]["id"]) == id_equipe), comp["competitors"][0])
    eux = next(c for c in comp["competitors"] if c is not nous)
    statut = comp.get("status", {}).get("type", {})
    m = {
        "date": ev["date"],
        "competition": (ev.get("league") or {}).get("name") or ev.get("seasonType", {}).get("name") or "",
        "adversaire": eux["team"].get("displayName") or eux["team"].get("name"),
        "logo_adversaire": ((eux["team"].get("logos") or [{}])[0]).get("href") or eux["team"].get("logo"),
        "domicile": nous.get("homeAway") == "home",
        "lieu": (comp.get("venue") or {}).get("fullName"),
        "tv": [b.get("media", {}).get("shortName") for b in comp.get("broadcasts", []) if b.get("media")][:2],
        "termine": bool(statut.get("completed")),
        "id": ev["id"],
        "ligue": ((ev.get("league") or {}).get("slug") or ""),
    }
    if m["termine"]:
        a, b = score(nous), score(eux)
        if a is not None and b is not None:
            m["score"] = f"{a}-{b}"
            m["resultat"] = "V" if float(a) > float(b) else "D" if float(a) < float(b) else "N"
    return m


class Limite(Exception):
    """Wikipédia demande de ralentir : on arrête les recherches pour cette fois."""


def photo_wikipedia(nom: str, sport: str) -> dict | None:
    for langue in ("en", "fr"):
        time.sleep(1.2)  # Wikipédia limite le nombre de requêtes : une par seconde environ
        try:
            d = get(f"https://{langue}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(nom.replace(" ", "_")))
        except urllib.error.HTTPError as ex:
            if ex.code == 429:
                raise Limite() from ex
            continue
        except Exception:
            continue
        desc = (d.get("description") or "").lower() + " " + (d.get("extract") or "")[:200].lower()
        if d.get("type") == "standard" and d.get("thumbnail") and any(m in desc for m in MOTS_WIKI[sport]):
            return {"photo": d["thumbnail"]["source"], "credit": "Wikimedia Commons"}
    return None


LIGUES_FOOT = ["esp.1", "uefa.champions", "esp.copa_del_rey", "esp.super_cup", "fifa.cwc"]
POSTES_FR = {
    "soccer": {
        "G": "Gardien", "RB": "Latéral droit", "LB": "Latéral gauche", "CD": "Défenseur central",
        "CD-L": "Défenseur central", "CD-R": "Défenseur central", "DM": "Milieu défensif",
        "CM": "Milieu", "CM-L": "Milieu", "CM-R": "Milieu", "LM": "Milieu gauche", "RM": "Milieu droit",
        "AM": "Milieu offensif", "AM-L": "Ailier gauche", "AM-R": "Ailier droit", "LW": "Ailier gauche",
        "RW": "Ailier droit", "F": "Attaquant", "CF": "Avant-centre", "CF-L": "Attaquant", "CF-R": "Attaquant",
    },
    "football": {
        "QB": "Quarterback", "RB": "Running back", "WR": "Receveur", "TE": "Tight end", "LT": "Tackle gauche",
        "LG": "Garde gauche", "C": "Centre", "RG": "Garde droit", "RT": "Tackle droit", "LDE": "Défensif gauche",
        "RDE": "Défensif droit", "LDT": "Tackle défensif", "RDT": "Tackle défensif", "NT": "Nose tackle",
        "WLB": "Linebacker", "MLB": "Linebacker", "SLB": "Linebacker", "LILB": "Linebacker", "RILB": "Linebacker",
        "LCB": "Cornerback", "RCB": "Cornerback", "NB": "Nickel back", "SS": "Safety", "FS": "Safety",
    },
    "basketball": {"PG": "Meneur", "SG": "Arrière", "G": "Arrière", "SF": "Ailier", "F": "Ailier", "PF": "Ailier fort", "C": "Pivot"},
}


POSTES_LONGS = {
    "Goalkeeper": "Gardien", "Defender": "Défenseur", "Midfielder": "Milieu", "Forward": "Attaquant",
    "Quarterback": "Quarterback", "Running Back": "Running back", "Wide Receiver": "Receveur",
    "Tight End": "Tight end", "Offensive Tackle": "Tackle offensif", "Guard": "Garde", "Center": "Centre",
    "Defensive End": "Défensif de ligne", "Defensive Tackle": "Tackle défensif", "Linebacker": "Linebacker",
    "Cornerback": "Cornerback", "Safety": "Safety", "Place kicker": "Botteur", "Place Kicker": "Botteur", "Punter": "Punter",
    "Long Snapper": "Long snapper", "Point Guard": "Meneur", "Shooting Guard": "Arrière",
    "Small Forward": "Ailier", "Power Forward": "Ailier fort", "Offensive Lineman": "Ligne offensive",
    "Defensive Lineman": "Ligne défensive", "Defensive Back": "Arrière défensif", "Athlete": "Polyvalent",
}


def poste_long(sport: str, nom: str) -> str:
    if sport == "basketball":
        return {"Guard": "Arrière", "Forward": "Ailier", "Center": "Pivot"}.get(nom, POSTES_LONGS.get(nom, nom))
    return POSTES_LONGS.get(nom, nom)


def poste_fr(sport: str, abbr: str) -> str:
    if abbr in ("SUB", ""):
        return ""  # remplaçant : on reprend le poste de l'effectif
    return POSTES_FR.get(sport, {}).get(abbr, abbr)


def code(p: dict) -> str:
    return (p.get("position") or {}).get("abbreviation", "")


def fiche_joueur(nom, poste, numero, joueurs, photo=None):
    j = joueurs.get(cle(nom), {})
    f = {"nom": nom, "poste": poste or j.get("poste", ""), "numero": str(numero or j.get("numero", ""))}
    if photo or j.get("photo"):
        f["photo"] = photo or j["photo"]
    return f


def composition(e: dict, eq: dict, joueurs: dict, maintenant) -> dict | None:
    """Titulaires : officiels du prochain match s'ils sont publiés, sinon ceux du dernier match.
    NFL : titulaires de la hiérarchie (depth chart). Football universitaire : joueurs clés du dernier match."""
    base = f"{ESPN}/{e['sport']}/{e['ligue']}"
    if e["ligue"] == "nfl":
        d = get(f"{base}/teams/{e['equipe']}/depthcharts")
        blocs = []
        groupes = d.get("depthchart", [])
        attaque = [g for g in groupes if "WR" in g.get("name", "") or "offense" in g.get("name", "").lower()]
        defense = [g for g in groupes if g.get("name", "").rstrip().endswith(" D") or "defense" in g.get("name", "").lower()]
        for titre_bloc, dc in (("Attaque", (attaque or [None])[0]), ("Défense", (defense or [None])[0])):
            if not dc:
                continue
            titulaires = []
            for cle_poste, pos in dc.get("positions", {}).items():
                ath = (pos.get("athletes") or [None])[0]
                if not ath:
                    continue
                abbr = (pos.get("position") or {}).get("abbreviation") or cle_poste.upper()
                titulaires.append(fiche_joueur(ath["displayName"], poste_fr("football", abbr), ath.get("jersey"), joueurs))
            blocs.append({"titre": titre_bloc, "schema": dc.get("name", ""), "joueurs": titulaires})
        return {"type": "hierarchie", "titre": "Titulaires (hiérarchie actuelle)", "blocs": blocs}

    candidats = []
    prochain = (eq.get("prochains") or [None])[0]
    if prochain and datetime.fromisoformat(prochain["date"].replace("Z", "+00:00")) - maintenant < timedelta(hours=3):
        candidats.append(("officielle", prochain))
    if eq.get("dernier"):
        candidats.append(("dernier", eq["dernier"]))

    for genre, m in candidats:
        ligues = [m.get("ligue")] + LIGUES_FOOT if e["sport"] == "soccer" else [e["ligue"]]
        for lg in [l for l in ligues if l]:
            try:
                s = get(f"{ESPN}/{e['sport']}/{lg}/summary?event={m['id']}")
            except Exception:
                continue
            titre = ("Composition officielle" if genre == "officielle" else "Titulaires du dernier match")
            contexte = {"adversaire": m["adversaire"], "date": m["date"], "score": m.get("score"), "resultat": m.get("resultat"), "domicile": m["domicile"]}
            if e["sport"] == "soccer":
                r = next((r for r in s.get("rosters", []) if eq["nom"] and r["team"]["displayName"] == eq["nom"] and r.get("roster")), None)
                if not r:
                    continue
                tit = [p for p in r["roster"] if p.get("starter")]
                tit.sort(key=lambda p: int(p.get("formationPlace") or 99))
                return {"type": "terrain", "titre": titre, "match": contexte, "formation": r.get("formation"),
                        "joueurs": [dict(fiche_joueur(p["athlete"]["displayName"], poste_fr("soccer", code(p)), p.get("jersey"), joueurs), place=int(p.get("formationPlace") or 0), code=code(p)) for p in tit],
                        "remplacants": [fiche_joueur(p["athlete"]["displayName"], poste_fr("soccer", code(p)), p.get("jersey"), joueurs) for p in r["roster"] if not p.get("starter") and p.get("subbedIn")]}
            box = s.get("boxscore", {}).get("players", [])
            nous = next((t for t in box if t["team"]["displayName"] == eq["nom"]), None)
            if not nous:
                continue
            if e["sport"] == "basketball":
                st = nous["statistics"][0]
                tit = [a for a in st["athletes"] if a.get("starter")]
                if not tit:
                    continue
                return {"type": "liste", "titre": "Cinq de départ du dernier match" if genre == "dernier" else "Cinq de départ", "match": contexte,
                        "joueurs": [fiche_joueur(a["athlete"]["displayName"], poste_fr("basketball", (a["athlete"].get("position") or {}).get("abbreviation", "")), a["athlete"].get("jersey"), joueurs, (a["athlete"].get("headshot") or {}).get("href")) for a in tit]}
            # Football universitaire : le meilleur joueur de chaque catégorie
            noms_cat = {"passing": "Passes", "rushing": "Course", "receiving": "Réception", "defensive": "Défense"}
            cles = []
            for st in nous["statistics"]:
                if st.get("name") in noms_cat and st.get("athletes"):
                    a = st["athletes"][0]["athlete"]
                    cles.append(fiche_joueur(a["displayName"], noms_cat[st["name"]], a.get("jersey"), joueurs, (a.get("headshot") or {}).get("href")))
            if cles:
                return {"type": "liste", "titre": "Joueurs clés du dernier match", "match": contexte, "joueurs": cles}
    return None


CATEGORIES_FR = {"Points": "Points", "Assists": "Passes déc.", "Rebounds": "Rebonds", "Sacks": "Sacks", "Tackles": "Plaquages",
                 "Passing Yards": "Passes", "Rushing Yards": "Course", "Receiving Yards": "Réception"}


def tops(e: dict, eq: dict, joueurs: dict) -> list:
    """Meilleurs joueurs de l'équipe au dernier match (NBA, NFL, NCAA) ou buteurs (football)."""
    m = eq.get("dernier")
    if not m:
        return []
    ligues = ([m.get("ligue")] + LIGUES_FOOT) if e["sport"] == "soccer" else [e["ligue"]]
    for lg in [l for l in ligues if l]:
        try:
            s = get(f"{ESPN}/{e['sport']}/{lg}/summary?event={m['id']}")
        except Exception:
            continue
        if e["sport"] == "soccer":
            buts = []
            for k in s.get("keyEvents", []):
                if "goal" in ((k.get("type") or {}).get("text") or "").lower() and (k.get("team") or {}).get("displayName") == eq["nom"]:
                    for p in (k.get("participants") or [])[:1]:
                        nom = p["athlete"]["displayName"]
                        f = fiche_joueur(nom, "But", "", joueurs)
                        f["valeur"] = (k.get("clock") or {}).get("displayValue", "")
                        buts.append(f)
            if s.get("keyEvents") is not None:
                return buts
            continue
        for t in s.get("leaders", []):
            if (t.get("team") or {}).get("displayName") != eq["nom"]:
                continue
            res = []
            for cat in t.get("leaders", []):
                if not cat.get("leaders"):
                    continue
                l = cat["leaders"][0]
                f = fiche_joueur(l["athlete"]["displayName"], CATEGORIES_FR.get(cat.get("displayName"), cat.get("displayName", "")), l["athlete"].get("jersey"), joueurs, (l["athlete"].get("headshot") or {}).get("href"))
                v = l.get("displayValue", "")
                for en, fr in ((" YDS", " yds"), (" CAR", " courses"), (" REC", " réc."), (" INT", " int."), (" TD", " TD")):
                    v = v.replace(en, fr)
                f["valeur"] = v
                res.append(f)
            return res[:4]
    return []


# College football sur Disney+ (France) : depuis avril 2026, l'espace ESPN de Disney+ reprend les
# matchs diffusés aux États-Unis sur les chaînes du groupe Disney, mais ne les met pas en avant (on ne
# les trouve qu'en cherchant une équipe). On les liste à partir de la chaîne indiquée par ESPN.
# Règle vérifiée le 2026-11-17 en cherchant 15 matchs dans Disney+ France :
# - chaînes ESPN/ABC, SEC Network, ACC Network, SECN+ : tous présents ;
# - ESPN+ : présents seulement quand l'équipe qui reçoit est en SEC, ACC, Big 12 ou American (3/3) ;
#   absents pour la Sun Belt, la Conference USA et la MAC (0/4).
CHAINES_DISNEY = {"ABC", "ESPN", "ESPN2", "ESPNU", "ESPNEWS", "SEC Network", "ACC Network", "SECN+", "ACCNX", "ACCN+", "LHN", "Disney+"}
CONF_ESPN_PLUS = {"1", "4", "8", "151"}  # identifiants ESPN : ACC, Big 12, SEC, American


def college_disney(maintenant: datetime, jours: int = 9) -> list:
    matchs = {}
    for i in range(jours):
        # Journées américaines : un match du samedi soir aux États-Unis tombe le dimanche à Paris.
        jour = (maintenant - timedelta(hours=8) + timedelta(days=i)).strftime("%Y%m%d")
        d = get(f"{ESPN}/football/college-football/scoreboard?dates={jour}&groups=80&limit=300")
        for ev in d.get("events", []):
            comp = ev["competitions"][0]
            chaines = []
            for b in comp.get("geoBroadcasts", []) + comp.get("broadcasts", []):
                n = (b.get("media") or {}).get("shortName") or ((b.get("names") or [None])[0])
                if n and n not in chaines:
                    chaines.append(n)
            recoit = next((c for c in comp["competitors"] if c.get("homeAway") == "home"), comp["competitors"][0])
            tv = [c for c in chaines if c in CHAINES_DISNEY]
            if not tv and "ESPN+" in chaines and str(recoit["team"].get("conferenceId")) in CONF_ESPN_PLUS:
                tv = ["ESPN+"]
            if not tv:
                continue
            statut = comp.get("status", {}).get("type", {})
            debut = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            if statut.get("completed") and debut < maintenant - timedelta(hours=12):
                continue
            equipes = {}
            for c in comp["competitors"]:
                t = c["team"]
                rang = (c.get("curatedRank") or {}).get("current") or 99
                equipes[c.get("homeAway", "home")] = {
                    "nom": t.get("location") or t.get("displayName"),
                    "surnom": t.get("name") or "",
                    "abr": t.get("abbreviation") or "",
                    "logo": t.get("logo") or "",
                    "rang": rang if rang <= 25 else None,
                    "bilan": ((c.get("records") or [{}])[0]).get("summary") or "",
                    "score": score(c) if statut.get("state") != "pre" else None,
                }
            if "home" not in equipes or "away" not in equipes:
                continue
            matchs[ev["id"]] = {
                "id": ev["id"],
                "date": ev["date"],
                "chaine": tv[0],
                "etat": statut.get("state"),  # pre, in, post
                "detail": statut.get("shortDetail") or "",
                "neutre": bool(comp.get("neutralSite")),
                "titre": ((comp.get("notes") or [{}])[0]).get("headline", ""),  # nom du bowl, finale…
                "dom": equipes["home"],
                "ext": equipes["away"],
            }
    return sorted(matchs.values(), key=lambda m: m["date"])


def main() -> int:
    conf = json.loads(SUJETS.read_text(encoding="utf-8"))
    ancien = json.loads(SORTIE.read_text(encoding="utf-8")) if SORTIE.exists() else {}
    joueurs_avant = ancien.get("joueurs", {})
    maintenant = datetime.now(timezone.utc)
    sortie = {"genere_le": maintenant.isoformat(timespec="minutes"), "equipes": {}, "joueurs": {}}
    erreurs = 0
    etat_wiki = {"limite": False}

    for theme in conf["themes"]:
        for sujet in theme["sujets"]:
            e = sujet.get("espn")
            if not e:
                continue
            base = f"{ESPN}/{e['sport']}/{e['ligue']}/teams/{e['equipe']}"
            cal = f"{ESPN}/{e['sport']}/{e.get('ligue_calendrier', e['ligue'])}/teams/{e['equipe']}/schedule?fixture=true"
            try:
                d = get(cal)
                id_eq = str(d["team"]["id"])
                evs = sorted(d.get("events", []), key=lambda x: x["date"])
                # Un calendrier « fixture » ne contient que les matchs à venir : on ajoute les résultats.
                try:
                    passes = get(cal.replace("?fixture=true", "")).get("events", [])
                except Exception:
                    passes = []
                tous = {x["id"]: x for x in passes + evs}
                evs = sorted(tous.values(), key=lambda x: x["date"])
                futurs = [match(x, id_eq) for x in evs if datetime.fromisoformat(x["date"].replace("Z", "+00:00")) > maintenant - timedelta(hours=3)]
                futurs = [m for m in futurs if not m["termine"]]
                joues = [match(x, id_eq) for x in evs]
                joues = [m for m in joues if m["termine"]]
                sortie["equipes"][sujet["id"]] = {
                    "nom": d["team"].get("displayName"),
                    "logo": ((d["team"].get("logo") or "") if isinstance(d["team"].get("logo"), str) else "") or ((d["team"].get("logos") or [{}])[0]).get("href"),
                    "prochains": futurs[:3],
                    "dernier": joues[-1] if joues else None,
                }
                print(f"{sujet['id']:<16} {len(futurs)} matchs à venir, dernier : {joues[-1]['score'] if joues and 'score' in joues[-1] else '—'}")
            except Exception as ex:
                erreurs += 1
                print(f"[erreur] calendrier {sujet['id']}: {ex}", file=sys.stderr)
                if sujet["id"] in ancien.get("equipes", {}):
                    sortie["equipes"][sujet["id"]] = ancien["equipes"][sujet["id"]]

            try:
                r = get(f"{base}/roster")
                groupes = r.get("athletes", [])
                effectif = []
                for g in groupes:
                    effectif += g["items"] if isinstance(g, dict) and "items" in g else [g]
                avec = 0
                for j in effectif:
                    nom = j.get("fullName") or j.get("displayName")
                    if not nom:
                        continue
                    fiche = {
                        "nom": nom,
                        "equipe": sujet["id"],
                        "poste": poste_long(e["sport"], (j.get("position") or {}).get("displayName") or ""),
                        "numero": j.get("jersey") or "",
                    }
                    if (j.get("headshot") or {}).get("href"):
                        fiche.update(photo=j["headshot"]["href"], credit="ESPN")
                    else:
                        avant = joueurs_avant.get(cle(nom), {})
                        if "photo" in avant:
                            fiche.update(photo=avant["photo"], credit=avant.get("credit", ""))
                        elif not etat_wiki["limite"] and avant.get("essai_wiki", "") < (maintenant - timedelta(days=7)).isoformat():
                            try:
                                w = photo_wikipedia(nom, e["sport"])
                                if w:
                                    fiche.update(w)
                                else:
                                    fiche["essai_wiki"] = maintenant.isoformat(timespec="minutes")
                            except Limite:
                                etat_wiki["limite"] = True
                                print("[info] Wikipédia demande de ralentir : suite des photos au prochain passage", file=sys.stderr)
                        elif "essai_wiki" in avant:
                            fiche["essai_wiki"] = avant["essai_wiki"]
                    avec += "photo" in fiche
                    sortie["joueurs"][cle(nom)] = fiche
                print(f"{'':<16} effectif {len(effectif)}, {avec} avec photo")
            except Exception as ex:
                erreurs += 1
                print(f"[erreur] effectif {sujet['id']}: {ex}", file=sys.stderr)
                for k, v in joueurs_avant.items():
                    if v.get("equipe") == sujet["id"]:
                        sortie["joueurs"][k] = v

    # Compositions (après les effectifs, pour retrouver les photos)
    for theme in conf["themes"]:
        for sujet in theme["sujets"]:
            e = sujet.get("espn")
            eq = sortie["equipes"].get(sujet["id"])
            if not e or not eq:
                continue
            try:
                if eq.get("dernier"):
                    eq["dernier"]["tops"] = tops(e, eq, sortie["joueurs"])
            except Exception as ex:
                print(f"[erreur] tops {sujet['id']}: {ex}", file=sys.stderr)
            try:
                eq["composition"] = composition(e, eq, sortie["joueurs"], maintenant)
            except Exception as ex:
                erreurs += 1
                print(f"[erreur] composition {sujet['id']}: {ex}", file=sys.stderr)
                eq["composition"] = (ancien.get("equipes", {}).get(sujet["id"]) or {}).get("composition")

    try:
        cfb = college_disney(maintenant)
        sortie["college_disney"] = {"genere_le": maintenant.isoformat(timespec="minutes"), "matchs": cfb}
        print(f"college football sur Disney+ : {len(cfb)} matchs")
    except Exception as ex:
        erreurs += 1
        print(f"[erreur] college football Disney+: {ex}", file=sys.stderr)
        if "college_disney" in ancien:
            sortie["college_disney"] = ancien["college_disney"]

    # Joueurs ajoutés à la main par la routine (cités dans un résumé, hors effectif) : on les garde.
    for k, v in joueurs_avant.items():
        if v.get("equipe") == "autre" and k not in sortie["joueurs"]:
            sortie["joueurs"][k] = v

    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ data/sport.json ({erreurs} erreurs)")
    return 0 if sortie["equipes"] else 1


if __name__ == "__main__":
    sys.exit(main())
