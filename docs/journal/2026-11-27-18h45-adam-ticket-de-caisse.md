# 2026-11-27 18h45 : adam : ticket de caisse → liste de courses

- **Agent / personne** : Claude Code piloté par Adam
- **Branche** : `main`
- **Lot** : 1 (interface et parcours)

## Fait

- Résolution des conflits entre les comptes de Jade et les magasins OpenStreetMap, fusion poussée.
- Ajout d'un ticket de caisse par photo : bouton sur la page de la liste, route `POST /panier/ticket`,
  lecture par RapidOCR, analyse des lignes, écran de vérification (corriger, retirer) puis ajout en
  mode « le moins cher équivalent » (`POST /panier/ticket/ajouter`).
- Mots collés recoupés (« PATESSPAGHETTI » → « pâtes spaghetti »), une cinquantaine d'abréviations,
  regroupement en lignes qui suit l'inclinaison d'une photo penchée.
- Dockerfile : `libgl1` et `libglib2.0-0` pour opencv.
- Vérifié dans le navigateur : photo → 5 articles lus → un retiré → 4 ajoutés.

## Fichiers modifiés

- `app/panier/ticket.py` (nouveau) : lecture OCR, regroupement en lignes, analyse et nettoyage des libellés.
- `app/panier/routes.py` : route `POST /panier/ticket`.
- `app/templates/panier/page.html` : champ « photo d'un ticket de caisse » et zone `#ticket-lu`.
- `app/templates/panier/_ticket.html` (nouveau) : articles lus, modifiables.
- `app/templates/panier/_liste_maj.html` : vide `#ticket-lu` après l'ajout.
- `app/static/style.css` : styles du formulaire de ticket.
- `Dockerfile` : bibliothèques système d'opencv.
- `pyproject.toml`, `uv.lock` : dépendance `rapidocr_onnxruntime`.
- `tests/test_ticket.py` (nouveau), `docs/decisions.md`.

## Reste à faire

- Essayer avec de vraies photos de tickets (testé seulement sur des images générées) et compléter
  le vocabulaire et les abréviations de `app/panier/ticket.py`.

## Points d'attention pour la suite

- La première lecture charge le modèle (quelques secondes), les suivantes environ 3 s par ticket.
- Après le `git pull`, chacun relance `uv sync` (RapidOCR et onnxruntime : environ 450 Mo).
