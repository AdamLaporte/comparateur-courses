# 2026-11-27 15h08 : claude : cadrage et conception

- **Agent / personne** : Claude Code (prénom de la personne au clavier non précisé)
- **Branche** : `main` (commit initial)
- **Lot** : mise en place, étapes 1 (cadrage) et 2 (conception)

## Fait

- Cadrage avec l'équipe, une question à la fois :
  - Collecte Carrefour, E.Leclerc Drive et Courses U : conçue comme dans le cahier des charges, implémentée plus
    tard avec Codex.
  - Ligne de liste au choix : produit précis (EAN) ou « le moins cher équivalent ».
  - Démo en local, mise en ligne si le temps le permet.
  - Intermarché : **pas de clé** (demande pas encore approuvée). Sans clé, aucune requête et repli direct.
  - Architecture A retenue : FastAPI + Jinja2 + HTMX + SSE.
- Recherches :
  - Portail Intermarché (APIs Stores v1 et Produits v1 « Deprecated », en-têtes et limites).
  - Test Carrefour demandé par l'équipe : curl reçoit 403 Cloudflare `cf-mitigated: challenge` sur `set-store/136`,
    donc la collecte automatique a été arrêtée. Dans un navigateur normal, `routeData` se lit bien (30 produits, prix
    du Drive 136, promotions dont fidélité).
  - coursesu.com (403 Cloudflare), leclercdrive.fr (403 DataDome).
  - Couverture d'Open Prices autour de Rennes et Bruz.
- Dépôt Git initialisé (`main`), `.gitignore`.
- Rédaction de `docs/architecture.md` (vue d'ensemble, séquence du parcours, modèle de données, contrat, interface,
  collecte et repli, notes techniques sur les sources), `AGENTS.md`, `CLAUDE.md`, `docs/decisions.md`,
  `docs/taches.md` et du modèle de journal.

## Fichiers modifiés

- `.gitignore` : secrets, `.env`, bases SQLite, caches Python et outils, cookies et pages d'essai.
- `AGENTS.md` : référence unique (objectif, techno, arborescence, commandes, conventions, Git, règles des agents).
- `CLAUDE.md` : `@AGENTS.md`.
- `docs/architecture.md` : architecture et 3 diagrammes Mermaid.
- `docs/decisions.md` : 20 décisions du 27/11.
- `docs/taches.md` : étapes de mise en place, grandes lignes des lots, risques.
- `docs/journal/MODELE.md` : modèle de journal.

## Reste à faire

- Validation de l'étape 2 par l'équipe.
- Étape 3 : installer uv, branche `feat/squelette`, projet et parcours de bout en bout avec données fictives, tests.
- Étape 4 : découpage détaillé des 4 lots dans `docs/taches.md` et attribution des personnes.

## Points d'attention pour la suite

- `uv` n'est pas installé sur cette machine (Python 3.14 système, Node 22).
- Aucune identité Git n'était configurée sur cette machine au moment du premier commit.
