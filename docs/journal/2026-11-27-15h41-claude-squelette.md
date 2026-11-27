# 2026-11-27 15h41 : claude : squelette

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `feat/squelette` (partie de `main` après la documentation)
- **Lot** : mise en place, étape 3 (squelette)

## Fait

- Installé `uv` 0.13.10 (installeur officiel d'Astral) et Python 3.13 via uv.
- Créé le projet uv : `pyproject.toml` (ruff, pytest), `uv.lock`, `.python-version`, `.env.example`.
- Dépendances : fastapi, uvicorn[standard], jinja2, httpx, pydantic-settings, itsdangerous, python-multipart,
  pwdlib[argon2], tzdata. Pour le développement : pytest, ruff.
- Écrit tout le code de l'arborescence prévue, organisé par fonctionnalité :
  - les fichiers partagés : `main.py`, `config.py`, `db.py`, `contrats.py`, `gabarits.py`, `sources/base.py` ;
  - la source fictive pour les 4 enseignes ;
  - les sources réelles en bouchons ; Intermarché n'envoie aucune requête sans clé ;
  - l'orchestrateur (asyncio, Semaphore et timeout par enseigne, repli) ;
  - le cache, le repli et le préchauffage, en bouchons ;
  - les magasins, avec le géocodage (table intégrée + API Adresse) ;
  - les produits, le panier (liste en SQLite, calcul, flux SSE, API JSON) ;
  - les comptes, en bouchon avec leurs tables ;
  - les templates HTMX et le CSS.
- Tests (17, tous verts, sans réseau) :
  - parcours JSON et HTML jusqu'au flux SSE ;
  - calcul : promo lot, fidélité, promo immédiate, manquants, classement ;
  - orchestrateur : enseigne lente, source en panne, concurrence ≤ 3, Intermarché sans clé = aucune requête ;
  - sources réelles pas encore branchées.
- Vérifié dans Chrome sur `http://localhost:8000` :
  - 35170 → 8 magasins fictifs → Nutella (produit précis) + « lait demi » (le moins cher) → Comparer ;
  - les cases se remplissent une à une, avec les totaux, les économies et le classement ;
  - chaque prix indique « Données fictives · heure » ;
  - une seule connexion SSE, fermée après `fin`.
- Documentation mise à jour : `AGENTS.md` (arborescence, commandes), `docs/architecture.md` (SSE natif,
  `gabarits.py`, `schema.sql`, clés de session, réglages, limites connues), `docs/decisions.md` (10 nouvelles
  lignes), `docs/taches.md` (statuts).

## Fichiers modifiés

- `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `Dockerfile`, `.dockerignore`
- `app/**` (tout le code), `data/demo/recherches.txt`, `tests/**`
- `AGENTS.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/taches.md`, ce journal

## Décisions prises

- Voir les lignes du 27/11 ajoutées en bas de `docs/decisions.md` :
  - SSE natif de FastAPI ;
  - `tzdata` ;
  - un `schema.sql` par fonctionnalité ;
  - `gabarits.py` partagé ;
  - `ReglagesDep` ;
  - E501 ignorée ;
  - règle du mode « équivalent » ;
  - EAN fictifs commençant par 2 ;
  - événement `fin`.

## Reste à faire

- Validation du squelette par l'équipe, puis fusion de `feat/squelette` dans `main` (en local, Adam pousse).
- Étape 4 : découpage détaillé des 4 lots dans `docs/taches.md` et attribution des personnes.

## Points d'attention pour la suite

- Le Dockerfile n'a pas été testé : l'utilisateur de cette machine n'a pas accès au démon Docker
  (`permission denied` sur `/var/run/docker.sock`).
- La page des résultats et le flux SSE recalculent chacun la liste des magasins. Avec de vraies sources, il faudra
  mettre cette liste en cache (voir `docs/architecture.md` §14).
- La recherche d'Open Food Facts a répondu 503 après une dizaine de requêtes rapprochées : le lot 4 doit espacer ses
  appels et mettre les résultats en cache.
- Les tests affichent un avertissement de Starlette (« install httpx2 ») sans conséquence pour l'instant.
