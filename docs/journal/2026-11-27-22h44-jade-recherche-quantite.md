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
- Recherche pendant la frappe (capture de Jade : « spag » donnait « SPAG », « Sauce à Spag »…) : le dernier mot est un
  début de mot (`spag*`), candidats triés par popularité, puis classement par nom le plus simple. Vérifié en vrai :
  « spag » → Spaghetti 500 g, « nute » → Nutella, « pain de mi » → Pain de mie, « banane » → Bananes,
  « papier toil » → Papier toilette. « Œufs » est maintenant reconnu (ligature).

## Fichiers modifiés

- `app/produits/service.py`
- `tests/test_produits.py`, `tests/donnees/off/recherche_nutella_quantite_400.json` et
  `tests/donnees/off/recherche_spag_prefixe.json` (réponses enregistrées le 27/11)
- `docs/decisions.md`

## Reste à faire

- Scénario de démo (tâche 6 du lot 4) avec Adam.

## Points d'attention pour la suite

- Une recherche fait 1 appel à Open Food Facts en général (début de mot), jusqu'à 3 avec une quantité ou peu de
  résultats (1 s d'écart entre deux appels). Ensuite tout vient du cache (7 jours).
