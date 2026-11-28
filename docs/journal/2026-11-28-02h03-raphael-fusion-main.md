# 2026-11-28 02h03 — Raphaël — fusion de main

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — intégration des extensions Carrefour et E.Leclerc Drive avec le menu Démo/Réel.

## Fait

- Repris la fusion entre `7b2e506` et `6485c67`. Vérifié que `docs/decisions.md` conserve les deux décisions à l’origine du conflit.
- Vérifié l’alignement de la documentation sur le bouton du menu. Les 202 tests passent, ainsi que le lint et le contrôle du formatage Ruff.

## Fichiers concernés

- `docs/decisions.md` conserve les entrées des deux commits. `README.md`, `docs/architecture.md` et `docs/taches.md` situent le bouton dans le menu.
- `app/static/style.css`, `app/templates/base.html` et `tests/test_mode_donnees.py` reprennent la version amont du bouton.

## Reste à faire

- Vérifier un relevé marchand Carrefour et E.Leclerc dans Edge.
