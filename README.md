# Le Fil

Une appli d'actualités personnelle : chaque matin, un résumé en français de ses sujets
(sport, IA & tech, luxe), avec les liens vers les articles. Les dépêches brutes sont mises à jour
toute la journée.

**Appli :** https://syncflanders.github.io/le-fil/ (à installer sur Android : Chrome → menu ⋮ → « Ajouter à l'écran d'accueil »)

## Comment ça marche (gratuit)

| Pièce | Rôle | Quand |
|---|---|---|
| `scripts/collecte.py` (GitHub Actions) | récupère les titres de Google Actualités et des sites spécialisés | 6 fois par jour, de 6 h 20 à 21 h 20 |
| Routine Claude (cloud, abonnement Claude) | lit les dépêches, trie, écrit le résumé (`ROUTINE.md`) | chaque matin à 7 h |
| `scripts/publier.py` | relie le résumé aux vrais liens, archive l'édition | appelé par la routine |
| `index.html` + `sw.js` | l'appli (PWA), lisible hors ligne | — |

## Ajouter ou modifier un sujet

Tout est dans `sujets.json` : demander à Claude Code « ajoute le sujet X à Le Fil ».
Il faut un `id`, un `titre`, une `consigne` (ce que je veux, ce que je ne veux pas), des
`requetes` Google Actualités et, si possible, des `flux` de sites spécialisés ou de passionnés.
Le changement est pris en compte à la collecte suivante.

## Tester en local

```
python3 scripts/collecte.py
python3 -m http.server 8765   # puis http://localhost:8765
```
