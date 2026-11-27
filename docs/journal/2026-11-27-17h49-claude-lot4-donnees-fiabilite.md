# 2026-11-27 : claude : lot 4, données et fiabilité

- **Agent / personne** : Claude Code (prénom de la personne qui pilote : à compléter)
- **Branche** : `claude/nifty-curie-x3h69j` (branche imposée par la session cloud, à fusionner comme `feat/donnees-fiabilite`)
- **Lot** : 4. Données et fiabilité

## Fait

- **Cache SQLite** (`app/collecte/cache.py`) : `lire_frais`, `lire_dernier` (marqué `cache`, date d'origine), `ecrire`
  (jamais de fictif), et cache des réponses des services ouverts (`lire_reponse`, `ecrire_reponse`). Tests.
- **Open Prices** (`app/sources/open_prices.py`) : lieu OSM de même enseigne le plus proche (moins de 2 km), relevés du
  lieu (pages en parallèle), `obtenir_prix` par EAN, `chercher_produits` par texte, `trouver_magasins` (magasins
  connus d'Open Prices, utile au lot 2 pour Intermarché sans clé). Tests sur des réponses enregistrées.
- **Repli** : même règle « équivalent » que l'orchestrateur (`equivalence.py`), lignes en retard traitées en
  parallèle. Testé de bout en bout : Intermarché sans clé → repli → Open Prices.
- **Référentiel produits** (`app/produits/service.py`) : Open Food Facts via `search.openfoodfacts.org`, reclassement,
  un appel par seconde au plus, cache 7 jours, table `produit`, catalogue fictif en secours. Vérifié en vrai sur les
  16 recherches de la démo.
- **Préchauffage** (`app/collecte/prechauffer.py`) : magasins, suggestions, collecte, bilan par magasin. Testé.
- Réglages ajoutés (commit à part) : `SOURCE_PRODUITS`, `OPEN_PRICES_ACTIF`, `OPEN_FOOD_FACTS_RECHERCHE_URL`.
- 47 tests verts, ruff propre.

## Fichiers modifiés

- `app/config.py`, `.env.example`, `tests/conftest.py` : 3 réglages (partagés, ajouts seulement)
- `app/collecte/cache.py`, `schema.sql` (table `cache_reponse`), `repli.py`, `orchestrateur.py`, `equivalence.py`
  (nouveau), `prechauffer.py`
- `app/sources/open_prices.py`
- `app/produits/service.py`, `app/produits/schema.sql` (nouveau, table `produit`)
- `data/demo/recherches.txt` : commentaire (lignes EAN possibles)
- `tests/test_cache.py`, `tests/test_open_prices.py`, `tests/test_produits.py` (nouveaux), `tests/test_orchestrateur.py`
- `tests/donnees/open_prices/*.json`, `tests/donnees/off/*.json` : réponses enregistrées le 27/11
- `docs/architecture.md`, `docs/decisions.md`, `docs/taches.md`

## Décisions prises

- Voir les lignes du 27/11 « lot 4 » dans `docs/decisions.md`.

## Reste à faire

- Tâche 6 : jeu de démo avec le lot 1 (code postal, articles, magasins bien couverts).
- Samedi matin : lancer le préchauffage avec les vraies sources activées dans `.env`.
- Mode « fin de mois » (bonus) : `app/collecte/equivalence.py` est le point d'accroche.

## Points d'attention pour la suite

- **Open Prices couvre très mal Rennes** : presque aucun relevé de moins de 2 ans, aucun lieu à Bruz. Le vrai filet
  pour la démo, c'est le cache des prix réels rempli par le préchauffage. Sinon, les données fictives (marquées).
- Lot 1 : le filtre `releve` n'affiche pas l'année. Pour un prix Open Prices ancien, l'année est dans `source_detail`.
- Lot 2 : `SourceOpenPrices(reglages).trouver_magasins(position, rayon, max)` donne les magasins connus d'Open Prices
  (identifiants `<enseigne>-op-<id du lieu>`).
- Lots 2 et 3 : donner une `ville` aux magasins de `data/magasins/*.json` aide Open Prices à trouver le lieu.
- Mode « équivalent » par texte : « lait » peut trouver « Lait de coco ». Pour la démo, préférer des lignes « produit »
  (EAN choisi dans les suggestions).
