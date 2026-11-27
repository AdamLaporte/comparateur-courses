# 2026-11-27 21h00 — Raphaël — ouverture automatique des onglets Edge

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — collecte Edge depuis le panier.

## Fait

- Les deux extensions enregistrent l’activation et ouvrent un onglet à la réception d’une tâche.
  Le retrait est vérifié avant la recherche. Les pauses de collecte restent disponibles dans le popup.
- Le serveur local peut démarrer Edge sur Windows quand un prix manque et que les extensions ne
  répondent pas. Le réglage a été activé dans le `.env` local et le serveur a redémarré.
- Les 98 tests Python et les deux contrôles Ruff passent. Le test Edge simulant le démarrage sans
  onglet, le dépôt Super U et le défi Intermarché affiche `DRIVES_COLLECTEUR_OK`.

## Fichiers modifiés

- `app/drives/panier.py`, `app/drives/navigateur.py`, `app/config.py` et `.env.example`.
- Dossiers des extensions, tests Edge et Python, guide et documentation d’architecture.

## Reste à faire

- Charger les extensions 1.4 dans le profil Edge utilisateur. Un relevé réel sur les sites marchands
  reste à confirmer avec ces extensions activées.
