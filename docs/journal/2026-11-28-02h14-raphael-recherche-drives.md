# 2026-11-28 02h14 — Raphaël — recherche des drives autour de Bruz

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — recherche de magasins et comparaison en mode Réel.

## Fait

- Reproduit l’absence de Carrefour et E.Leclerc en mode Réel. Le catalogue initial ne contenait que des points Courses U et Intermarché, et les bases locales n’avaient aucun point inscrit depuis Edge.
- Ajouté Carrefour Drive Chartres-de-Bretagne (`267`) et E.Leclerc Drive Bruz – Ker Lann (`113511`). Le service inclut les points géolocalisés absents du fichier OpenStreetMap et fusionne les fiches de même identifiant.
- Adapté la collecte E.Leclerc pour lancer la recherche depuis l’adresse du catalogue obtenue après sélection du point. La référence doit correspondre au point demandé avant et après la recherche.
- Testé la recherche à 5 km de Bruz, les colonnes du comparatif et la file Edge des quatre enseignes. Les 203 tests passent, ainsi que les contrôles Ruff.
- Relancé les instances locale et partagée. Vérifié en mode Réel que la recherche `35170` à 5 km affiche Carrefour et E.Leclerc sur les deux instances.

## Fichiers modifiés

- `app/drives/points_retrait.json`, `app/drives/modeles.py`, `app/drives/catalogue.py`, `app/drives/routes.py` et `app/magasins/service.py` pour le catalogue et sa prise en compte dans la recherche.
- `extensions-edge/leclerc/collecteur.js` et `extensions-edge/leclerc/manifest.json` pour l’ouverture du catalogue marchand.
- `tests/test_mode_donnees.py`, `tests/test_drives.py`, `tests/test_ticket.py`, `docs/architecture.md`, `docs/decisions.md` et `docs/taches.md`.

## Reste à faire

- Contrôler le premier relevé marchand Carrefour et E.Leclerc dans Edge. La fiche Carrefour donne la route de sélection et la référence E.Leclerc figure dans le lien marchand publié pour Ker Lann. [Carrefour](https://www.carrefour.fr/magasin/market-chartres-de-bretagne) · [E.Leclerc Drive](https://www.leclercdrive.fr/region-bretagne/bruz/drive-bruz---ker-lann.aspx) · [Lien du catalogue Ker Lann](https://emplettes.net/35/bruz/e-leclerc-drive-bruz-ker-lann-g44)
- Reprendre la synchronisation Git. Le rebase sur `2217689` a rencontré un conflit dans `docs/decisions.md` et a été annulé pour effectuer le correctif sur le `main` local.
