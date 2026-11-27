# 2026-11-27 : jade : quantité dans la recherche d'articles

- **Agent / personne** : Claude Code piloté par Jade
- **Branche** : `main`
- **Lot** : 4. Données et fiabilité (référentiel produits)

## Fait

- « nutella 400 g » ne renvoyait rien sur Open Food Facts (les mots « 400 » et « g » étaient cherchés dans le nom) :
  le site retombait sur le catalogue fictif. Corrigé : la quantité est retirée des mots, une recherche ciblée sur le
  champ `quantity` est faite d'abord, puis la recherche générale complète.
- Les produits de la quantité demandée passent en tête, unités converties (1 kg = 1000 g, 1 L = 100 cl = 1000 ml,
  packs « 6 x 1 L » comptés au total).
- Vérifié sur le vrai service : « nutella 400 g », « nutella 1kg », « lait demi-écrémé 1L », « coca-cola 1,5 L »,
  « beurre doux 250g » donnent la bonne quantité en tête ; « nutella » seul ne change pas.
- Tests : `lire_quantite`, `separer_quantite`, recherche ciblée sur une réponse enregistrée.

## Fichiers modifiés

- `app/produits/service.py`
- `tests/test_produits.py`, `tests/donnees/off/recherche_nutella_quantite_400.json` (réponse enregistrée le 27/11)
- `docs/decisions.md`

## Reste à faire

- Scénario de démo (tâche 6 du lot 4) avec Adam.

## Points d'attention pour la suite

- Une recherche avec quantité fait jusqu'à 2 appels à Open Food Facts (1 s d'écart) : la première suggestion arrive
  environ une seconde plus tard, ensuite tout vient du cache.
