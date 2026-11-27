# 2026-11-27 22h50 — Raphaël — plusieurs magasins par extension Edge

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`, avancée jusqu’à `f669550`.
- **Lot** — extension des relevés de prix à plusieurs points de retrait.

## Fait

- Ajouté un catalogue de points de retrait, avec les deux drives de Bruz, Hyper U Guichen
  et Intermarché Rennes Gayeulles.
- Les extensions Edge 1.6 prennent les tâches par enseigne, ouvrent le magasin demandé dans
  le même onglet et vérifient le retrait avant le dépôt. Chaque magasin conserve ses prix.
- Les 114 tests et les contrôles Ruff passent. Les deux scénarios Edge simulés vérifient le
  changement de magasin et le refus d’un retrait qui ne correspond pas.
- Serveur partagé redémarré. Les deux nouveaux points apparaissent via Tailscale et la route
  de collecte refuse les requêtes anonymes.

## Fichiers modifiés

- Catalogue et service des drives, association OSM, contrôle d’accès, extensions et tests.
- README, guide du site partagé, architecture, décisions et tâches.

## Reste à faire

- Recharger les extensions sur les postes de collecte et vérifier un relevé marchand réel
  dans les deux nouveaux points de retrait.
