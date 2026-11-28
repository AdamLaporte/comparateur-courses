# 2026-11-28 02h29 — Raphaël — relevé manuel Edge

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — relevé manuel de Carrefour et E.Leclerc Drive.

## Fait

- Le bouton « Relever cette page » distinguait mal les pages sans référence de retrait et les échecs de lecture du catalogue du comparateur. Les deux magasins de démo sont bien présents dans le catalogue de l’instance partagée.
- Carrefour 1.0.2 et E.Leclerc 1.0.3 permettent d’enregistrer et d’exporter en CSV des prix dont la référence est vérifiée dans la page, y compris si le catalogue est indisponible. Une page sans référence exploitable indique où ouvrir les prix du Drive.
- Vérifié dans Edge le refus d’une page sans référence, l’export local en cas de panne et la priorité donnée à la fiche du comparateur. Les 203 tests pytest et les contrôles Ruff passent.

## Fichiers modifiés

- `popup.js` et `manifest.json` des extensions Carrefour et E.Leclerc.
- `tests/donnees/drives/releve_manuel.html`, `docs/architecture.md`, `docs/decisions.md` et `docs/taches.md`.

## Reste à faire

- Vérifier le relevé sur les pages marchandes du poste de collecte après rechargement des extensions.
