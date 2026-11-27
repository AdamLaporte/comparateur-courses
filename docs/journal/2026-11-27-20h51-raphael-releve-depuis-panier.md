# 2026-11-27 20h51 — Raphaël — relevé Edge depuis le panier

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — intégration des drives de Bruz au parcours du panier.

## Fait

- Supprimé la page dédiée et ses liens. Le bouton « Comparer » déclenche les relevés manquants pour
  les deux points de retrait. Le flux du panier affiche les états, les derniers prix connus et les totaux.
- Associé les fiches OSM aux identifiants marchands. Le retrait Courses U est à La Haye de Pan.
- Ajouté la confirmation de connexion dans les deux extensions et documenté le parcours depuis l’accueil.
- Vérifié le flux du panier avec Edge simulé et le tableau réel sur le serveur local, qui reste lancé.

## Fichiers modifiés

- `app/collecte/`, `app/drives/`, `app/magasins/service.py`, `app/panier/` et `app/contrats.py`.
- Gabarits du panier et des magasins, navigation principale et dossiers des extensions Edge.
- `tests/test_drives.py`, `README.md` et documents d’architecture, de décisions et de tâches.

## Reste à faire

- Charger les deux extensions du dépôt dans Edge et valider un relevé marchand réel. Le profil inspecté
  contient une ancienne copie de Super U sans collecteur automatique et aucune extension Intermarché.
