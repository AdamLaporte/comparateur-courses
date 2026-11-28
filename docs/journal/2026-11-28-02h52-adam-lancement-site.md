# 2026-11-28 02h52 : adam : lancement du site

- **Agent / personne** : Claude Code piloté par Adam
- **Branche** : `main`
- **Lot** : aucun (lancement local)

## Fait

- `uv sync` puis serveur lancé sur http://127.0.0.1:8000 (`uvicorn app.main:app --reload`).
- Vérifié : accueil, feuille de style, `/magasins?code_postal=35170` et `/api/magasins?code_postal=35170`
  répondent 200 ; l'API renvoie des magasins réels autour de Bruz.

## Fichiers modifiés

- `docs/journal/2026-11-28-02h52-adam-lancement-site.md` : ce journal (aucun autre fichier modifié).

## Décisions prises

- Aucune.

## Reste à faire

- Rien pour cette session ; voir `docs/taches.md` avant la démo.

## Points d'attention pour la suite

- Tests et ruff non relancés (aucun code modifié) ; pas de `git pull` fait avant le lancement.
