# 2026-11-28 01h37 — Raphaël — relance du comparateur

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main` à `52178fc`.
- **Lot** — redémarrage du comparateur et vérification Edge.

## Fait

- Les ports 8000 et 8001 étaient libres. Démarré le comparateur local sur 8000 et l’instance Tailscale sur 8001, avec leurs configurations et bases existantes.
- Vérifié l’accueil local et l’accueil authentifié via Tailscale. Les deux catalogues Edge répondent en HTTPS et la nouvelle table des points de retrait existe dans les deux bases.

## Fichiers modifiés

- Ce journal de session. Les journaux Uvicorn sont dans `.venv/serveurs/`.

## Reste à faire

- Le premier relevé marchand après l’ajout d’un point de retrait reste à tester.
