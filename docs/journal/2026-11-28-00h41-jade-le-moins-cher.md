# 2026-11-28 : jade : « le moins cher » (sujet du produit, prix à l'unité)

- **Agent / personne** : Claude Code piloté par Jade
- **Branche** : `main`
- **Tâche** : bugs de la comparaison en mode « le moins cher »

## Fait

- « lait » ne choisit plus « Gâteau au chocolat au lait » : le produit doit avoir la recherche pour sujet (premier
  mot important du nom, sans la marque ni « gros », « bio », « boîte de »). « oeufs » écarte « Pâtes aux œufs ».
  Si aucune offre n'a ce sujet, on garde toutes les offres.
- Choix au prix à l'unité (gramme, millilitre ou pièce), calculé depuis le format : « boîte de 12 », « x6 »,
  « 6 gros œufs », « 500 g », « 6 x 1 L ».
- Prix ramenés à une même quantité pour tous les magasins (choix de Jade) : celle tapée (« oeufs x12 ») ou sinon le
  format du premier prix trouvé ; la case indique « prix ramené à 12 unités ».
- Même règle pour les drives, la source de l'enseigne et Open Prices.
- Tests : `tests/test_equivalence.py` (14 tests).

## Fichiers modifiés

- `app/collecte/equivalence.py`, `app/collecte/orchestrateur.py`, `app/collecte/repli.py`
- `app/drives/comparaison.py` (le choix des drives passe la recherche), `app/panier/calcul.py` (`reference`),
  `app/panier/routes.py` (quantité de référence par ligne)
- `tests/test_equivalence.py` ; `tests/test_drives_comparaison.py` : sans format, le carré frais de 200 g
  (1,25 €/100 g) bat celui de 100 g (1,60 €/100 g)
- `docs/decisions.md`, `docs/architecture.md`

## Points d'attention pour la suite

- La référence est le format du premier prix trouvé : elle peut changer d'une comparaison à l'autre si les drives
  répondent dans un autre ordre. Pour un format fixe, taper le format (« oeufs x12 »).
- Un produit dont le format est illisible (« 450 » sans unité) est comparé à son prix affiché.
