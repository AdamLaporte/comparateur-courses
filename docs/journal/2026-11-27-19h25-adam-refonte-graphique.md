# 2026-11-27 19h25 : adam : refonte graphique (lot 1)

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `main`
- **Lot** : 1 (interface et parcours)

## Fait

- Charte « étiquette de rayon et ticket de caisse » dans `app/static/style.css` (variables en tête de fichier) :
  Archivo étroit et gras pour les titres et les prix, IBM Plex Mono pour les relevés, jaune « promo » pour
  l'action principale, vert pour les économies, couleur des enseignes en repère seulement.
- Toutes les pages refaites : en-tête et menu (page active soulignée), accueil (titre, recherche du lieu, choix de
  la distance en pastilles, ticket « mode d'emploi »), magasins (liste numérotée + carte Leaflet liée à la liste),
  ma liste (recherche + liste en vis-à-vis), comparaison (verdict, classement façon ticket, tableau avec colonne
  des articles fixe, prix le plus bas de chaque ligne et colonne gagnante mis en avant), comptes et page d'erreur.
- Icônes SVG (`app/templates/_icones.html`) à la place des émojis ; filtre `etiquette` dans `app/gabarits.py`.
- `app/static/site.js` : « Me localiser », carte, mise en avant, recherche vidée après un ajout.
- Vérifié dans Chrome sur ordinateur et en largeur téléphone (390 px) : accueil, magasins, liste, comparaison en
  direct, compte, favoris, erreur. 75 tests verts, ruff propre.

## Fichiers modifiés

- `app/static/style.css`, nouveau `app/static/site.js`
- `app/templates/` : `base.html`, `erreur.html`, nouveau `_icones.html`, `magasins/*`, `panier/*`,
  `produits/_suggestions.html`, `comptes/page.html` (icône de la maison)
- `app/gabarits.py` (ajout du filtre `etiquette`), `tests/test_comptes.py` (texte du bouton maison sans émoji)
- `AGENTS.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/taches.md`, ce journal

## Reste à faire

- Scénario de démo avec le lot 4 (articles bien couverts, préchauffage).
- Polices, HTMX et Leaflet viennent de jsdelivr : sans Internet le jour de la démo, le site reste utilisable mais
  perd ses polices, sa carte et HTMX. Si la salle n'a pas de réseau, copier ces fichiers dans `app/static/`.
- Images des produits (Open Food Facts) : possible, demanderait un champ en plus dans `Produit` (lot 4).
