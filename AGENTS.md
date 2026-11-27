# AGENTS.md : référence unique du projet

> Ce fichier est lu par Claude Code (via `CLAUDE.md`), Codex et les humains de l'équipe.
> Il fait foi pour l'objectif, la technologie, l'arborescence, les commandes, les conventions et les règles.

## Règle n°1 (obligatoire pour tout agent)

**Tout agent lit `AGENTS.md` et `docs/taches.md` avant de commencer, et écrit son fichier de journal avant de
terminer sa session.**

Le journal est un nouveau fichier `docs/journal/AAAA-MM-JJ-HHhMM-prenom-sujet.md`. Il indique la branche, ce qui a
été fait, les fichiers modifiés et ce qui reste à faire. Modèle :
[`docs/journal/MODELE.md`](docs/journal/MODELE.md). `prenom` est le prénom de la personne qui pilote l'agent, ou
`claude` / `codex` s'il n'est pas connu. Un fichier par session évite les conflits Git.

## Objectif

Site qui compare le prix d'un panier de courses entre les supermarchés proches d'un étudiant, en France.

1. **Magasins à proximité** : code postal → magasins Carrefour, Intermarché, Courses U et E.Leclerc Drive autour.
2. **Prix du panier** : liste de courses → prix de chaque article dans chaque magasin proche → total par magasin,
   promotions comprises. Chaque ligne est soit un **produit précis** (EAN), soit « **le moins cher équivalent** »
   (recherche texte).
3. **Avec ou sans compte** : tout marche sans compte. Avec un compte : articles favoris et adresses favorites.

Fonctionnalités secondaires, prévues dans le modèle mais pas promises : mode « fin de mois », fidélité et avantages
étudiants, trajet, répartition sur plusieurs magasins. Voir `docs/architecture.md` §12.

**Deadline : samedi 28 novembre 2026, 13h.** Entre deux options, on choisit celle qui donne une démo fonctionnelle
à temps.

## Technologie

- Python 3.13, dépendances gérées avec **uv**.
- **FastAPI** dans un seul processus : pages **Jinja2** + **HTMX**, prix au fil de l'eau en **SSE**
  (SSE intégré à FastAPI, `fastapi.sse`, + extension SSE de HTMX 2), API JSON sous `/api/...`.
- Schémas **Pydantic** v2 (`app/contrats.py`) : le contrat entre interface, serveur et sources.
- **httpx** asynchrone pour les appels externes, **asyncio** pour le parallélisme.
- **SQLite** via le module `sqlite3` de Python, sans ORM.
- Tests **pytest**, formatage et lint **ruff**.
- Sources de données : Open Food Facts (référentiel produits), API Intermarché (clé pas encore obtenue), collecte
  Carrefour / E.Leclerc Drive / Courses U, Open Prices (secours), données fictives (développement).

Détails et diagrammes : [`docs/architecture.md`](docs/architecture.md). Décisions : [`docs/decisions.md`](docs/decisions.md).

## Arborescence

```text
.
├── AGENTS.md                  # ce fichier
├── CLAUDE.md                  # contient seulement « @AGENTS.md »
├── pyproject.toml, uv.lock, .python-version
├── .env.example               # modèle de configuration (copier en .env, jamais commité)
├── Dockerfile, .dockerignore  # déploiement facultatif
├── app/
│   ├── main.py                # crée l'app, inclut tous les routers (partagé, ne bouge plus)
│   ├── config.py              # réglages (.env), tous pré-déclarés (partagé)
│   ├── db.py                  # connexion SQLite + création des tables (partagé)
│   ├── contrats.py            # schémas Pydantic communs (partagé, modification concertée)
│   ├── gabarits.py            # moteur Jinja2 commun + filtres euros/releve (partagé)
│   ├── sources/               # interface SourcePrix + une source par fichier
│   │   ├── base.py            # interface commune (partagé, modification concertée)
│   │   ├── registre.py        # quelle source pour quelle enseigne
│   │   ├── fictive.py         # données fictives (toujours marquées)
│   │   ├── intermarche.py     # API officielle (aucune requête sans clé)
│   │   ├── carrefour.py, leclerc.py, coursesu.py   # collecte en direct
│   │   └── open_prices.py     # source de secours
│   ├── collecte/              # orchestrateur.py, repli.py, cache.py, prechauffer.py, schema.sql
│   ├── magasins/              # routes.py, service.py (distances), geocodage.py
│   ├── produits/              # routes.py, service.py (recherche d'articles)
│   ├── panier/                # routes.py (liste, flux SSE, API), service.py, calcul.py, schema.sql
│   ├── comptes/               # routes.py, service.py, schema.sql (inscription, connexion, favoris)
│   ├── templates/             # base.html, erreur.html + un dossier par fonctionnalité
│   └── static/style.css
├── data/demo/recherches.txt   # recherches pour préchauffer le cache avant la démo
├── tests/                     # conftest.py, test_parcours.py, test_calcul.py, test_orchestrateur.py
└── docs/
    ├── architecture.md        # architecture et diagrammes (à jour)
    ├── decisions.md           # une ligne par décision importante
    ├── taches.md              # lots, qui fait quoi, statut
    └── journal/               # un fichier par session d'agent
```

> État au 27/11 (squelette) : parcours complet avec données fictives. Les modules marqués « BOUCHON » en tête de
> fichier (sources réelles, cache, Open Prices, comptes, préchauffage) sont à remplir par les lots.

## Commandes

Toutes les commandes se lancent à la racine du dépôt. `uv run` utilise le `.venv` du projet : pas besoin de
l'activer (si vous préférez, `source .venv/bin/activate` puis les commandes sans `uv run`).

```bash
# Installer uv (une seule fois par machine)
curl -LsSf https://astral.sh/uv/install.sh | sh                                  # Linux / macOS
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

uv sync                                   # installer les dépendances (crée .venv)
cp .env.example .env                      # configuration locale, à compléter si besoin
uv run uvicorn app.main:app --reload      # lancer le site → http://localhost:8000
uv run pytest                             # lancer les tests
uv run ruff format .                      # formater
uv run ruff check --fix .                 # vérifier (lint)
uv run python -m app.collecte.prechauffer data/demo/recherches.txt --code-postal 35170   # remplir le cache (lot 4)

# Parcours de démo : http://localhost:8000 → 35170 → « Composer ma liste » → « nutella », « lait » → « Comparer »
```

Avant chaque fusion dans `main` : `uv run pytest` vert, `uv run ruff format --check .` et `uv run ruff check .`
propres.

## Conventions

- **Langue** : documentation, commits, messages à l'utilisateur et noms métier en **français**. Dans le code, pas
  d'accents dans les identifiants (`trouver_magasins`, `prix_centimes`), en `snake_case`. Les classes sont en
  `PascalCase` (`SourcePrix`, `TotalMagasin`).
- **Montants** en centimes entiers (`int`). Dates en UTC dans le code, affichées à l'heure de Paris.
- **Identifiant de magasin** : `"<enseigne>-<id_enseigne>"` (ex. `carrefour-136`), utilisable dans le HTML et les
  noms d'événements SSE.
- **Routes** : pages HTML sans préfixe, JSON sous `/api/`. Les fragments HTMX sont des templates dont le nom commence
  par `_`.
- **Tables SQLite** : chaque fonctionnalité déclare les siennes (`CREATE TABLE IF NOT EXISTS`) dans son module.
- **Tests** : `tests/test_<fonctionnalite>.py`. **Aucun appel réseau dans les tests** : on utilise la source fictive
  ou des réponses enregistrées dans `tests/donnees/`.
- **Affichage des prix** : chaque prix indique sa source et l'heure du relevé. Les données fictives sont toujours
  marquées (`est_fictif=True`, mention « Données fictives »). Jamais d'erreur brute affichée à l'utilisateur.

## Git

- **Responsable du dépôt : Adam** (compte GitHub `AdamLaporte`). Il crée le dépôt distant, ajoute les autres
  participants et gère les fusions dans `main` et les envois (`push`).
- Chacun configure sa propre identité Git sur sa machine (`git config --global user.name "Prénom Nom"` et
  `git config --global user.email "..."`, idéalement l'adresse « noreply » de son compte GitHub).
- `main` reste **toujours fonctionnelle**. On travaille sur une branche par fonctionnalité : `feat/<nom>`
  (ex. `feat/collecte-carrefour`), `fix/<nom>` ou `docs/<nom>`.
- Petits commits, messages clairs en français : `type : description`, où `type` vaut `feat`, `fix`, `docs`, `test`,
  `refactor` ou `chore` (ex. `feat : lecture du JSON routeData de Carrefour`).
- On fusionne dans `main` seulement si les tests et ruff passent.
- **Les agents ne poussent jamais et ne créent pas de dépôt distant** : les humains s'en occupent.

## Règles pour les agents

1. Lire `AGENTS.md` et `docs/taches.md` avant de commencer. Lire `docs/architecture.md` avant de toucher à la
   structure.
2. Écrire son fichier dans `docs/journal/` avant de terminer la session (voir la règle n°1).
3. Ne modifier **que les fichiers de son lot** (voir `docs/taches.md`). Les fichiers partagés (`app/main.py`,
   `app/config.py`, `app/db.py`, `app/contrats.py`, `app/gabarits.py`, `app/sources/base.py`,
   `app/templates/base.html`) ne reçoivent que des **ajouts**, annoncés dans `docs/decisions.md` et commités à part.
4. Tenir à jour : `docs/taches.md` (statut de son lot), `docs/decisions.md` (une ligne par décision importante :
   date, décision, raison), `docs/architecture.md` (dès que la structure change).
5. Le reste de l'application ne dépend que de l'interface `SourcePrix`. Une nouvelle source implémente
   `trouver_magasins`, `chercher_produits` et `obtenir_prix`, lève `SourceIndisponible` ou `SourceNonConfiguree` en
   cas de problème, et n'affiche jamais rien elle-même.
6. **Collecte** : on ne contourne **jamais** une protection anti-robots. Pas d'imitation d'empreinte TLS, pas de
   rotation d'adresses IP ni de proxys, pas de résolution de captcha, pas de navigateur automatisé pour franchir un
   défi. Requêtes modérées avec des en-têtes de navigateur normaux. On utilise de préférence le JSON que le site
   charge lui-même, et Playwright seulement si c'est indispensable. Un 403 ou un défi déclenche le repli.
7. **Intermarché** : sans `INTERMARCHE_API_KEY`, aucune requête vers l'API ; la source passe directement au repli.
8. **Secrets** : ne jamais commiter `.env`, une clé, un cookie ou un mot de passe. Les nouveaux réglages vont dans
   `app/config.py` et `.env.example` (valeur vide ou fictive).
9. Ne pas ajouter de dépendance, de service ou d'abstraction sans besoin réel. Pas de microservices. Docker seulement
   pour le déploiement.
10. Lancer `uv run pytest` et `uv run ruff check .` avant chaque commit qui touche au code.
