# 2026-11-27 20h05 : adam : ticket de caisse, articles rapprochés des produits en magasin

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `main`
- **Lot** : 1 (parcours) et panier

## Fait

- Après la lecture d'un ticket, chaque article est rapproché d'un produit vendu en magasin (recherche
  produits ; si rien : sans les tailles « 400 g », puis premier mot). Une liste déroulante propose les produits
  trouvés et « Inexistant en magasins ». Corriger le texte d'un article relance la recherche pour cette ligne.
- Un article sans produit est ajouté en mode `inexistant` : affiché dans la liste (« inexistant en magasins »),
  dans le tableau sur une ligne grisée, mais jamais cherché ni compté dans les totaux.
- Nouveau mode `ModeLigne.INEXISTANT` (`app/contrats.py`), contrainte de `ligne_liste` élargie et migration des
  bases existantes au démarrage (`app/panier/service.migrer`, appelée dans `app/main.py`).
- Tests : `tests/test_ticket.py` adapté (champ `choix`) + cas « inexistant » + nouvelle recherche. 83 tests verts.
- Vérifié dans Chrome avec une image de ticket lue par l'OCR et Open Food Facts réel.

## Reste à faire

- Le premier produit proposé n'est pas toujours le bon format (ex. Nutella 825 g pour « nutella 400 g ») :
  l'utilisateur choisit dans la liste. On pourrait favoriser le produit dont la quantité correspond.
