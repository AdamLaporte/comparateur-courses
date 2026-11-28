# 2026-11-28 : adam : un prix pour chaque article en mode démo

- **Agent / personne** : Claude Code piloté par Adam
- **Branche** : `main`
- **Tâche** : compléter les données fictives avant la démo

## Fait

- Source fictive : articles courants ajoutés, prix garanti pour tout article dans tout magasin.
- Recherche fictive : début de mot (plus de correspondance au milieu d’un mot), quantités ignorées, « œ » reconnu.
- Vérifié : pytest, ruff, 25 articles comparés dans 5 magasins en démo (125 cases, aucune vide).

## Fichiers modifiés

- `app/sources/fictive.py`, `app/panier/routes.py`, `app/templates/panier/_resultats.html`, `tests/test_ticket.py`, `app/collecte/orchestrateur.py`, `tests/test_fictive.py`, `docs/decisions.md`

## Reste à faire

- Chacun fait `git pull --rebase` avant de reprendre.

## Points d’attention pour la suite

- Un article hors catalogue s’affiche avec le texte tapé, sans marque ni format, entre 1,50 € et 6,50 € environ.
- « hors catalogue : cherché sur les drives » ne s’affiche plus qu’en mode réel ; la liste garde le badge
  « inexistant en magasins » dans les deux modes.
