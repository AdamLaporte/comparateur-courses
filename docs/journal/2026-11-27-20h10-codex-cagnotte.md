# Tirelire des économies

- **Agent** Codex
- **Branche** `feat/cagnotte-economies`
- **Lots** Interface et comptes

## Fait

- Calcul de la moyenne des paniers complets, arrondie au centime, et confirmation du magasin choisi.
- Cumul SQLite des écarts signés et affichage de la tirelire dans le compte.
- Confirmation unique par comparaison et validation du magasin côté serveur.
- Ajout d'un bouton sur le cochon qui affiche sept pièces au clic, avec prise en compte de la préférence de mouvement réduit. Les 23 tests de comptes passent.

## Fichiers modifiés

- Comptes, schéma SQLite, flux des résultats, gabarits, feuille de style, tests de comptes et suivi des tâches.

## Reste à faire

- Valider le rendu de la tirelire dans un navigateur.
