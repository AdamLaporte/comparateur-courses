# 2026-11-28 01h28 — Raphaël — ajouter des points de retrait partout en France

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`, alignée sur `origin/main` à `fb9f116`.
- **Lot** — extension des relevés Edge U et Intermarché au-delà du catalogue initial.

## Fait

- Ajouté le formulaire Edge qui détecte le retrait actif et soumet sa référence, sa fiche officielle et son adresse au comparateur.
- Enregistré les nouveaux points de retrait dans SQLite après géocodage avec le code postal confirmé. La comparaison en mode Données réelles récupère ensuite le point et ses relevés par référence.
- Conservé les identifiants des points du catalogue initial et accepté les nouveaux points dans l’import CSV et la collecte via Tailscale.
- Vérifié l’ajout, la création de la tâche et le prix dans le panier pour les deux enseignes. Les 200 tests pytest, Ruff et les simulations Edge des extracteurs, des collecteurs et des deux formulaires passent.

## Fichiers modifiés

- `app/drives/`, `app/acces_partage.py`, `app/magasins/`, `app/collecte/orchestrateur.py`, `app/mode_donnees.py` et `app/templates/magasins/liste.html` — inscription, géocodage, liste de magasins et file de collecte.
- `extensions-edge/` — ajout du retrait actif dans les deux extensions, version 1.7.0.
- `tests/test_drives.py`, `tests/test_site_partage.py` et `tests/donnees/drives/navigateur.html` — inscription de nouveaux points et relevés simulés.
- `README.md`, `docs/architecture.md`, `docs/decisions.md` et `docs/taches.md` — parcours et couverture.

## Reste à faire

- Vérifier une inscription et un relevé par enseigne dans le navigateur du poste de collecte. Les annuaires ont renvoyé 403 lors du téléchargement direct. Le nouveau parcours ajoute les points depuis la session Edge au fur et à mesure.
