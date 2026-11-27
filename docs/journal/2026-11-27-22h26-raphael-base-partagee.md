# 2026-11-27 22h26 — Raphaël — base de prix partagée

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — hébergement du comparateur partagé.

## Fait

- Remplacé le projet de déploiement alwaysdata par un hébergement sur le PC Windows de Raphaël.
- Ajouté un serveur partagé HTTPS derrière Tailscale Serve, deux accès Web, des jetons Edge
  révocables et une base SQLite distincte qui démarre vide. Le mode local garde sa base.
- Rendu l’adresse du serveur configurable dans les extensions 1.5.0. Les baux de collecte sont
  associés au collecteur autorisé.
- Installé Tailscale, confirmé la connexion du PC et lancé la configuration de Serve.
- Mis en service le site partagé via Tailscale. Uvicorn écoute
  sur le port 8001 en boucle locale. Les deux accès Web répondent via Tailscale et la base
  commune contient zéro observation au démarrage.
- Les 112 tests et les contrôles Ruff passent. Les tests couvrent les paniers séparés, la
  réutilisation du prix Nutella après redémarrage, la déduplication, le refus d’un mauvais jeton
  et la reprise d’une tâche différée. Le test simulé Edge et la vérification du frontal HTTPS
  via Uvicorn passent.

## Fichiers modifiés

- Configuration et lancement du site partagé, middleware d’accès et services de collecte.
- Extensions Edge, tests Python et contrôle du collecteur dans Edge.
- Guide de déploiement, README, architecture, décisions et tâches.

## Reste à faire

- Partager le PC hôte avec Adam et confirmer la réutilisation d’un relevé réel sur le second PC.
