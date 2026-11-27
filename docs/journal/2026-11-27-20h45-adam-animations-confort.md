# 2026-11-27 20h45 : adam : animations et confort d'usage

- **Agent / personne** : Claude Code (skill ui-ux-pro-max), session pilotée par Adam
- **Branche** : `main`
- **Lot** : 1 (interface)

## Fait

- Animations utiles : changement de page en fondu (en-tête fixe), lignes de la liste qui glissent à l'ajout
  et au retrait, bascule qui coulisse, nouvel article surligné, suggestions et magasins en cascade, repères de
  la carte qui se posent, titre et ticket animés sur l'accueil, progression réelle « 37 / 72 prix »,
  totaux qui clignotent quand ils changent, montant du verdict qui défile, étiquette « −x € » posée.
- Confort : quantités − / +, « Vider » et retrait avec « Annuler » (route `/panier/lignes/restaurer`), idées
  d'articles quand la liste est vide, Entrée ajoute « le moins cher » et ↓ ↑ parcourent les suggestions,
  indicateur de recherche, verdict même sans panier complet (« le plus complet »), prix marqués « à mettre à
  jour » au lieu d'être effacés, « Reprendre ma liste » sur l'accueil, « Comparer ma liste ici » sur les
  magasins (`?comparer=1`), itinéraire vers chaque magasin, barre « Comparer » fixe sur téléphone, bouton
  « Afficher » des mots de passe, boutons qui montrent l'attente.
- Tests : `tests/test_liste_confort.py` (6 tests). Vérifié dans Chrome (ordinateur et 390 px).

## Reste à faire

- Corrigé ensuite : le bouton « Afficher » héritait de la marge des boutons d'envoi ; `style.css` et `site.js`
  sont appelés avec `?v=<date de modification>` (`version_statique` dans `app/gabarits.py`) pour que le navigateur
  ne garde pas une ancienne version après un `git pull`.
- Vérifié : la transition entre pages se déclenche (type « page », Chrome).
- Non vérifié à l'œil : le glisser-déposer du ticket.
