# 2026-11-28 01h17 — Raphaël — relevés Edge hors Bruz

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`, synchronisée sur `fb9f116`.
- **Lot** — relevés Edge des points de retrait répertoriés.

## Fait

- Associé Hyper U Guichen à sa référence Courses U 36163 et conservé son identifiant interne pour retrouver ses relevés existants.
- Corrigé l’activation du retrait Intermarché si la fiche officielle change la casse ou ajoute un paramètre à l’adresse.
- Raccordé le relevé manuel au catalogue du serveur. Le CSV peut conserver le même produit relevé dans plusieurs magasins.
- Les 198 tests pytest, les contrôles Ruff et les deux scénarios Edge sur pages simulées passent.

## Fichiers modifiés

- `app/drives/` et `app/acces_partage.py` — référence marchande, catalogue authentifié et accès via Tailscale.
- `extensions-edge/` — lecture du retrait, ouverture du magasin, popup et version 1.6.2 des deux extensions.
- `tests/test_drives.py`, `tests/test_site_partage.py` et `tests/donnees/drives/` — vérifications du catalogue, de l’attribution des prix et du changement de magasin.
- `README.md`, `docs/architecture.md`, `docs/decisions.md` et `docs/taches.md` — couverture et procédure d’utilisation.

## Reste à faire

- Redémarrer le serveur du poste de collecte, recharger les extensions et vérifier un relevé sur les sites marchands à Guichen et Rennes Gayeulles. La requête de vérification directe vers Courses U a renvoyé 403.
