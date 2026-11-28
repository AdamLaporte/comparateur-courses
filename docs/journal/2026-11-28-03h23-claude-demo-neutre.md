# 2026-11-28 03h23 : claude : mode démo sans mention « fictif »

- **Agent / personne** : Claude Code (session cloud, pilote non nommé)
- **Branche** : `main` (commits locaux, non poussés : la session n'a pas d'accès en écriture au dépôt)
- **Lot** : Mode des données (voir `docs/taches.md`)

## Fait

- En mode démo, l'écran ne montre plus que les prix sont fictifs : libellé « Relevé en magasin », marques et
  magasins sans « (fictif) », adresses plausibles, identifiants `m12345` au lieu de `fictif-12345`, plus de note
  « contient des prix fictifs » dans le résumé, plus de couleur spéciale sur la source.
- Les prix de démo affichent la date du jour (« 28/11/2026 »), comme un relevé importé, au lieu de l'heure.
- Page Compte, « Options de démonstration » : un seul bouton, « Passer en démo » / « Quitter la démo ».
- Le marquage interne reste : `est_fictif=True` et `source=FICTIVE` (pas de cache, pas de mélange, pas d'Open Prices).
- Tests adaptés : en démo, ni le flux SSE ni la page Compte ne contiennent « fictif ».

## Fichiers modifiés

- `app/sources/fictive.py` : libellé affiché neutre, marques et magasins sans mention.
- `app/templates/panier/_case.html`, `app/templates/panier/_resume.html`, `app/panier/routes.py` : plus de marque visuelle.
- `app/templates/comptes/page.html`, `app/mode_donnees.py` : bouton et textes du mode.
- `tests/test_parcours.py`, `tests/test_mode_donnees.py`.
- `AGENTS.md`, `docs/decisions.md`, `docs/taches.md`.

## Reste à faire

- Pousser ces commits sur `main` (depuis un poste de l'équipe).

## Points d'attention pour la suite

- L'API JSON (`/api/...`) expose toujours `est_fictif` : c'est voulu (marquage interne).
- Annoncer à l'oral le passage en mode démo, et ne pas tirer le chiffre d'accroche du pitch de ces prix.
