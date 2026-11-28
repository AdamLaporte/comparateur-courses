# 2026-11-28 01h55 — Raphaël — extensions Carrefour et E.Leclerc Drive

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main` à `52178fc`.
- **Lot** — relevés Edge pour les deux enseignes restantes.

## Fait

- Créé deux extensions Edge chargeables séparément avec ajout du drive actif, relevé automatique pour la comparaison, relevé manuel et export CSV.
- Vérifié l’identité du drive par la référence des offres Carrefour et par le chemin du catalogue E.Leclerc. Les extensions refusent les résultats d’un autre drive et s’arrêtent sur les défis marchands.
- Étendu l’API de collecte et l’accès Tailscale. Relancé les deux serveurs et confirmé une réponse HTTP 200 des nouveaux catalogues avec leurs jetons.
- Les 202 tests pytest, Ruff et les deux scénarios des extensions dans Edge sur pages locales passent.

## Fichiers modifiés

- `extensions-edge/carrefour/` et `extensions-edge/leclerc/` — extensions 1.0.0 et adaptateurs marchands.
- `app/drives/modeles.py`, `app/acces_partage.py` et `app/templates/magasins/liste.html` — enregistrement et collecte des nouveaux points de retrait.
- `tests/test_drives.py`, `tests/test_site_partage.py` et `tests/donnees/drives/` — tests du panier, du partage et de la lecture des pages.
- `README.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/taches.md` et `docs/deploiement-partage.md` — installation et état des validations.

## Reste à faire

- Charger les extensions dans le profil Edge de collecte et valider un relevé marchand pour chaque enseigne. La recherche Carrefour a répondu 429 lors de la consultation externe et le catalogue E.Leclerc n’était pas accessible à l’outil de lecture.
