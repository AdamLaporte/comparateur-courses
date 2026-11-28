# 2026-11-28 02h23 — Raphaël — relevés Carrefour et E.Leclerc

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — relevés de prix Edge pour Chartres-de-Bretagne et Bruz – Ker Lann.

## Fait

- Confirmé dans la base partagée les échecs sur « Carré Frais » et « oeuf ». Carrefour a expiré pendant la lecture des résultats et E.Leclerc a échoué pendant la vérification initiale du catalogue.
- Carrefour 1.0.1 sélectionne le retrait et ouvre la recherche en une navigation. Si le site redirige vers son accueil, l’extension ouvre la recherche depuis cet accueil. Le collecteur extrait uniquement les tarifs portant la référence demandée.
- E.Leclerc 1.0.2 réutilise l’adresse d’un catalogue déjà ouvert lorsque sa référence concorde. Le collecteur distingue un retrait différent, un document sans référence et un chargement expiré.
- Les 203 tests pytest, Ruff et les deux scénarios Edge sur pages locales passent. Les scénarios vérifient la redirection Carrefour, les tarifs mélangés, le catalogue E.Leclerc déjà ouvert et l’arrêt sur défi.

## Fichiers modifiés

- `extensions-edge/carrefour/collecteur.js`, `drive.js`, `navigation.js` et `manifest.json`.
- `extensions-edge/leclerc/collecteur.js` et `manifest.json`.
- `tests/donnees/drives/collecteur.html`, `tests/donnees/drives/navigateur.html` et la documentation de suivi.

## Reste à faire

- Recharger les extensions dans Edge sur le poste de collecte et relancer le panier. Vérifier un relevé réel. L’URL du catalogue marchand après sélection de Ker Lann reste à confirmer.
