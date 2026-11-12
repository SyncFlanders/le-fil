# Routine du matin — rédiger l'édition du jour de Le Fil

Tu rédiges chaque matin l'édition de **Le Fil**, l'appli d'actualités personnelle de son lecteur.
Le lecteur lit l'édition sur son téléphone Android vers 7 h (heure de Paris). Il veut savoir,
en deux minutes, ce qui s'est passé d'important sur ses sujets, en français.

## Étapes

1. **Se mettre à jour.** `git pull --rebase origin main`.
2. **Vérifier la fraîcheur des dépêches.** Lis `genere_le` dans `data/depeches.json`.
   S'il date de plus de 6 heures, lance `python3 scripts/collecte.py` puis `python3 scripts/sport.py`. Si la collecte échoue
   (réseau bloqué), continue avec les dépêches existantes et signale-le dans `note`.
3. **Lire les consignes.** `sujets.json` donne, pour chaque sujet, ce que le lecteur veut
   et ne veut pas (`consigne`). Elles priment sur tout le reste.
4. **Lire les dépêches** de chaque sujet dans `data/depeches.json`. Ce sont des titres :
   presse (Google Actualités, `origine: presse`) et sites spécialisés ou de passionnés
   (`origine: passionnes`).
5. **Trier.** Pour chaque sujet, garde ce qui compte vraiment :
   - un fait nouveau (résultat, décision, nomination, annonce, chiffre) plutôt qu'un avis ;
   - un fait annoncé par **au moins deux sources**, ou par une source de référence
     (agence de presse, grand quotidien, site officiel du club ou de l'entreprise,
     presse spécialisée reconnue). Une rumeur à source unique peut figurer si elle est
     importante, mais elle est **présentée comme telle** (« selon X », « à confirmer ») ;
   - pas de pronostics de paris, de bons plans, d'offres d'emploi, de contenus
     d'agrégateurs douteux ou de sites générés automatiquement ;
   - attention aux homonymes (Rolls-Royce les moteurs d'avion ≠ Rolls-Royce les voitures,
     Crystal Palace ≠ un palace, Aman Feed ≠ Aman Resorts…).
   Pour un fait très important ou surprenant, tu peux faire une recherche web rapide
   pour confirmer. Ne fais pas plus de 5 recherches au total : la routine doit rester légère.
6. **Écrire `data/brouillon.json`** (format ci-dessous). Style :
   - français clair, phrases complètes, ton d'un bon journaliste de matinale ;
   - le résumé d'un sujet tient en 2 à 4 phrases ; les `points` en 2 à 4 puces courtes ;
   - chiffres précis quand ils existent, pas d'adjectifs creux ;
   - aucune information qui ne s'appuie pas sur une dépêche ou une recherche ;
   - si un sujet n'a rien de notable : `"resume": ""`, `"points": []`, `"articles": []`.
   Les `articles` sont des **morceaux exacts de titres** copiés depuis `data/depeches.json`
   (assez longs pour être uniques, 4 à 8 mots). Le script retrouve les liens : n'écris
   jamais d'URL toi-même. 3 à 6 articles par sujet, les plus utiles en premier.
   `joueurs` (sujets de sport seulement) : les noms complets des joueurs **cités dans le résumé**,
   du plus important au moins important, 4 au maximum (ex. `["Aaron Philo", "Vernell Brown III"]`).
   Le premier aura sa photo en tête de l'article. Le script retrouve photo et poste ; n'écris
   jamais d'URL d'image. Le prochain match, le dernier résultat et la composition s'affichent
   tout seuls (`data/sport.json`) : inutile de les répéter, sauf si l'actualité porte dessus.
   `a_la_une` : les 3 nouvelles les plus importantes de la journée, tous sujets confondus,
   avec l'`id` du sujet.
7. **Publier.** `python3 scripts/publier.py`. Corrige le brouillon si le script signale
   une erreur. Les avertissements « article introuvable » : remplace le morceau de titre.
8. **Enregistrer.**
   ```
   git add data/
   git commit -m "Édition du AAAA-MM-JJ"
   git pull --rebase origin main && git push origin HEAD:main
   ```
   Le site se met à jour tout seul quelques minutes après le push.
9. **Prévenir le lecteur (facultatif).** Si le fichier `NTFY_TOPIC` existe à la racine, envoie :
   `curl -s -H "Title: Le Fil est prêt" -H "Click: <url du site>" -d "<le titre de la première nouvelle à la une>" https://ntfy.sh/$(cat NTFY_TOPIC)`
   (l'URL du site est dans `README.md`). Si `curl` échoue, ce n'est pas bloquant.

## Format de `data/brouillon.json`

```json
{
  "date": "AAAA-MM-JJ",
  "note": "facultatif : un problème à signaler (collecte en échec…)",
  "a_la_une": [
    { "sujet": "anthropic", "titre": "Titre court et factuel", "texte": "Deux phrases au plus." }
  ],
  "themes": [
    {
      "id": "sport", "titre": "Sport",
      "sujets": [
        {
          "id": "real-madrid", "titre": "Real Madrid",
          "resume": "Deux à quatre phrases.",
          "points": ["Puce courte.", "Puce courte."],
          "articles": ["morceau exact du titre d'une dépêche", "…"],
          "joueurs": ["Prénom Nom", "…"]
        }
      ]
    }
  ]
}
```

Garde les mêmes thèmes et sujets, dans le même ordre que `sujets.json`.
La date est celle du jour à Paris (`TZ=Europe/Paris date +%F`).
