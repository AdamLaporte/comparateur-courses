# 2026-11-27 20h31 — Raphaël — comparateur des drives de Bruz

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`, avancée jusqu’à `f59e0d1` avant l’intégration.
- **Lot** — Drives de Bruz.

## Fait

- Recherche par point de retrait, observations SQLite, suivi HTMX et file de relevés avec bail.
- Ajout du mode automatique aux deux extensions Edge. Le relevé manuel et l’export CSV restent disponibles.
- Import de 1 520 observations d’Intermarché dans `data/app.db`. Un second import donne zéro ajout. Le
  catalogue Super U a été testé dans une base temporaire, avec 16 067 ajouts au premier passage et zéro au second.
- Vérification de la boucle serveur avec un collecteur simulé et des deux extracteurs sur une page locale dans Edge.
- Vérification de `/drives` sous Uvicorn et des prix importés via l’API. Les 94 tests, les deux vérifications
  Ruff et les contrôles de la page de test Edge passent.

## Fichiers modifiés

- `app/drives/`, `app/templates/drives/` et `extensions-edge/` pour le parcours et son protocole.
- `app/main.py`, `app/config.py`, `.env.example`, `app/templates/base.html` et
  `app/templates/magasins/liste.html` pour l’intégration.
- `tests/test_drives.py` et `tests/donnees/drives/navigateur.html` pour les vérifications.
- `README.md`, `docs/architecture.md`, `docs/decisions.md` et `docs/taches.md` pour la documentation.

## Décisions prises

- Les données importées gardent leurs dates. Les données initiales et le référentiel EAN restent facultatifs.
- Le relevé automatique lit un seul lot et refuse un résultat dont le retrait ou la requête est incertain.

## Reste à faire

- Confirmer le parcours marchand réel dans une session Edge utilisateur. Les essais isolés ont rencontré
  un défi sur chaque enseigne. Vérifier notamment le formulaire Super U, le signal de fin sans résultat
  et la preuve du retrait sur la page de recherche.
