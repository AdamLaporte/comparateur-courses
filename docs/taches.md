# Tâches

> À lire avant de commencer (règle n°1 d'`AGENTS.md`). Chacun tient à jour le statut de son lot ici.
> Statuts : `à faire`, `en cours`, `en attente de validation`, `fait`, `bloqué`.

## Mise en place (Claude Code)

| Étape | Contenu | Statut |
|---|---|---|
| 1. Cadrage | Questions, recherches sur les sources, choix de l'architecture A | fait |
| 2. Conception | `docs/architecture.md` (3 diagrammes), `AGENTS.md`, `CLAUDE.md`, `docs/decisions.md`, ce fichier, journal | fait |
| 3. Squelette | Projet uv, parcours de bout en bout avec données fictives, 17 tests. Fusionné dans `main` | fait |
| 4. Répartition | 4 lots indépendants (ci-dessous). Attribution des personnes : plus tard | fait |

## Comment travailler

1. `git clone https://github.com/AdamLaporte/comparateur-courses.git`, puis `uv sync` et
   `uv run uvicorn app.main:app --reload` → http://localhost:8000. Lire `AGENTS.md` et ce fichier.
2. Tout le monde travaille sur `main` (pas de branches) : `git switch main` puis `git pull --rebase` avant de commencer.
3. **Ne modifier que les fichiers de son lot** (tableau ci-dessous). Les fichiers partagés ne reçoivent que des ajouts,
   annoncés dans `docs/decisions.md`.
4. Avant de pousser : `uv run pytest`, `uv run ruff format .` et `uv run ruff check .`, statut mis à jour ici, journal
   écrit dans `docs/journal/`. Puis `git pull --rebase` et `git push`. Jamais de `--force`.
5. **Tout marche toujours avec les données fictives.** On active une vraie source dans son `.env`
   (`SOURCE_CARREFOUR=collecte`, etc.) seulement quand elle est prête. Personne n'attend personne.

## Qui possède quels fichiers

| Lot | Fichiers (création et modification libres) |
|---|---|
| 1. Interface et parcours | `app/templates/**`, `app/static/**`, `app/panier/routes.py`, `app/panier/calcul.py`, `app/produits/routes.py`, `app/magasins/routes.py`, `tests/test_parcours.py`, `tests/test_calcul.py` |
| 2. Intermarché, magasins et comptes | `app/sources/intermarche.py`, `app/magasins/service.py`, `app/magasins/geocodage.py`, `app/magasins/schema.sql` (à créer), `app/comptes/**`, `data/magasins/intermarche.json` (à créer), `tests/test_intermarche.py`, `tests/test_magasins.py`, `tests/test_comptes.py`, `tests/donnees/intermarche/**` |
| 3a. Carrefour | `app/sources/carrefour.py`, `data/magasins/carrefour.json`, `tests/test_carrefour.py`, `tests/donnees/carrefour/**` |
| 3b. E.Leclerc Drive | `app/sources/leclerc.py`, `data/magasins/leclerc.json`, `tests/test_leclerc.py`, `tests/donnees/leclerc/**` |
| 3c. Courses U | `app/sources/coursesu.py`, `data/magasins/coursesu.json`, `tests/test_coursesu.py`, `tests/donnees/coursesu/**` |
| 4. Données et fiabilité | `app/collecte/**`, `app/sources/open_prices.py`, `app/produits/service.py`, `app/produits/schema.sql` (à créer), `data/demo/**`, `tests/test_orchestrateur.py`, `tests/test_cache.py`, `tests/test_open_prices.py`, `tests/test_produits.py`, `tests/donnees/open_prices/**`, `tests/donnees/off/**` |
| Partagés (ajouts concertés) | `app/main.py`, `app/config.py`, `app/db.py`, `app/contrats.py`, `app/gabarits.py`, `app/sources/base.py`, `app/sources/registre.py`, `app/templates/base.html`, `pyproject.toml` (ajout de dépendance : prévenir Adam) |

## Lots

Le lot Drives de Bruz couvre le relevé via Edge, son intégration au panier et la documentation de
lancement. Le bouton « Comparer », le relevé simulé et l’import sont implémentés. La validation des
recherches sur les deux sites dans une session Edge configurée est en attente.
Le lancement du navigateur sous Windows et l’ouverture automatique des onglets après l’activation
initiale des extensions sont implémentés.

| Lot | Qui | Statut |
|---|---|---|
| 1. Interface et parcours | Adam (avec Claude Code) | refonte graphique faite (charte, accueil, carte des magasins, liste, comparaison, comptes) ; reste : scénario de démo avec le lot 4 |
| 2. Intermarché, magasins et comptes | magasins : à attribuer ; comptes : Jade (avec Claude Code) | magasins faits (OpenStreetMap, ville/position, rayon) ; comptes : connexion, articles favoris et « maison » faits ; cagnotte en attente de validation ; API Intermarché mise de côté |
| 3. Collecte web : 3a Carrefour, 3b E.Leclerc Drive, 3c Courses U (avec Codex) | à attribuer | à faire |
| 4. Données et fiabilité | Jade (avec Claude Code) | en cours : 1 à 5 faits, 6 (jeu de démo) à faire avec le lot 1 |

### Lot 1 : Interface et parcours

But : une démo claire et convaincante, qui marche quelles que soient les sources disponibles.

1. Page de résultats lisible sur l'écran de démo : panier le moins cher mis en avant, tableau qui reste lisible avec
   8 magasins (colonnes ou cartes, au choix), affichage correct sur téléphone.
2. Liste : modifier la quantité d'une ligne, vider la liste, garder la recherche après un ajout.
3. Affichage des sources : une étiquette par type (`api`, `collecte`, `open_prices`, `cache` avec la date
   « dernier prix connu du 26/11 », `fictive`), toujours avec l'heure du relevé.
4. Écrans des comptes (inscription, connexion, favoris) branchés sur les routes du lot 2.
5. Préparer le scénario de démo avec le lot 4 : code postal, liste d'articles, ce qu'on montre et dans quel ordre.

Fin : parcours de démo fluide sur l'ordinateur de démo, aucune erreur brute, `test_parcours.py` vert et complété.
Dépendances : aucune pour commencer, la source fictive suffit.

### Lot 2 : Intermarché, magasins et comptes

But : Intermarché utilisable avec ou sans clé, magasins réels de la zone de démo, comptes facultatifs.

1. **Dès maintenant, sans clé :**
   - Télécharger les specs OpenAPI Stores v1 et Produits v1 depuis le portail (bouton « download spec »).
   - Écrire la lecture des réponses à partir de leurs exemples : `produitEan13`, `libelle`, `marque`, `prix`,
     `prixBarre` (promo immédiate), `remise`, `dateDebut` / `dateFin`, `prixKg`.
   - Tests dans `tests/test_intermarche.py` avec les exemples enregistrés dans `tests/donnees/intermarche/`.
2. Liste fixe des magasins Intermarché de Rennes et Bruz dans `data/magasins/intermarche.json` (nom, adresse,
   coordonnées, identifiant `pdvRef` si connu, ou lieu Open Prices). `trouver_magasins` la renvoie quand il n'y a pas
   de clé.
3. **Risque clé** : vérifier le statut de la demande sur le portail ou écrire à ld_red_services@mousquetaires.com.
   C'est le ou la titulaire du compte du portail qui s'en charge.
4. Quand la clé arrive : appels réels, `X-Api-Key` pour Stores et `apikey` pour Produits. Respecter la limite de
   1 000 requêtes par heure : passer par le cache du lot 4.
5. Mettre en cache la liste des magasins par code postal (table `magasin`), pour que le tableau et le flux SSE voient
   les mêmes magasins (`docs/architecture.md` §14).
6. Comptes :
   - inscription et connexion par e-mail et mot de passe (`pwdlib` argon2) ;
   - `request.session["utilisateur_id"]` ;
   - articles favoris, adresses favorites.

   Option : à la connexion, rattacher à l'utilisateur la liste de sa session.

Fin : sans clé, toujours aucune requête (le test existant reste vert) ; la lecture des réponses est testée ; les
magasins Intermarché de la zone de démo s'affichent ; un compte permet d'enregistrer un article et une adresse.

### Lot 3 : Collecte web (sous-lots indépendants, avec Codex)

But : prix en direct de Carrefour, E.Leclerc Drive et Courses U quand les sites répondent, repli propre sinon.
Chaque sous-lot (3a, 3b, 3c) ne touche que son fichier et peut être confié à une session Codex séparée.

Pour chaque enseigne :
1. **Pages enregistrées par un humain** : dans un navigateur normal, choisir un magasin de la zone de démo, chercher
   2 ou 3 articles. Enregistrer la réponse « Document » ou le JSON utile (F12 → Réseau) dans
   `tests/donnees/<enseigne>/`.
2. **Parseur et tests** à partir de ces fichiers, sans réseau. Le parseur renvoie des `Prix` : EAN, libellé, prix,
   prix au kilo, promotions. Les promos fidélité deviennent `TypePromo.FIDELITE`, « 2e à -50 % » `LOT` et le prix
   barré `IMMEDIATE`. C'est la partie la plus sûre : à faire en premier.
3. **Magasins** : liste fixe de la zone de démo dans `data/magasins/<enseigne>.json`, avec l'identifiant utilisé par
   le site. Ou bien le JSON du localisateur de magasins s'il est accessible sans défi.
4. **Requêtes httpx** :
   - utiliser `nouveau_client()` et ses en-têtes de navigateur, avec délais et cookies de sélection du magasin ;
   - un 403, un en-tête `cf-mitigated: challenge` ou une page DataDome lèvent `SourceIndisponible` ;
   - **ne jamais contourner** (règle 6 d'`AGENTS.md`).
5. `obtenir_prix(magasin, ean)` : chercher par EAN si le site le permet, sinon par libellé puis filtrer sur l'EAN.

- **3a Carrefour** : repères complets dans l'annexe de `docs/architecture.md`. Le test du 27/11 portait sur le Drive
  136 « Rennes Centre Alma » : `set-store/136` sélectionne le Drive, `/s?q=` lance la recherche, et le prix se lit
  dans le JSON `routeData`.
- **3b E.Leclerc Drive** : leclercdrive.fr est protégé par DataDome. Repérer le JSON chargé par la page de recherche
  du Drive choisi.
- **3c Courses U** : coursesu.com est protégé par Cloudflare. Repérer le JSON chargé par la page de recherche du
  magasin choisi.

Fin de chaque sous-lot :
- le parseur est testé sur les fichiers enregistrés ;
- avec `SOURCE_<ENSEIGNE>=collecte`, l'enseigne affiche ses magasins et, si le site répond, ses prix ;
- un 403 fait passer au repli sans erreur visible.

### Lot 4 : Données et fiabilité

But : toujours un prix à montrer, daté et sourcé, et une démo préparée à l'avance.

1. **Cache SQLite** (`app/collecte/cache.py`, table `cache_prix`) : `lire_frais`, `lire_dernier`, `ecrire`, avec
   la durée `CACHE_TTL_MIN`. Tests.
2. **Open Prices** (`app/sources/open_prices.py`) :
   - prix récents par EAN pour un magasin ;
   - le magasin correspond au lieu OpenStreetMap de même enseigne le plus proche ;
   - tests sur des réponses enregistrées.

   Aider le lot 2 pour les magasins Intermarché connus d'Open Prices.
3. **Repli** (`app/collecte/repli.py`) : vérifier l'ordre cache daté → Open Prices → indisponible, et traiter les
   lignes en retard en parallèle.
4. **Référentiel produits** (`app/produits/service.py`) :
   - recherche Open Food Facts (texte → EAN, libellé, marque, quantité) ;
   - appels espacés (503 constatés au-delà d'une dizaine de recherches rapprochées) et mis en cache ;
   - catalogue fictif en secours.
5. **Préchauffage** (`app/collecte/prechauffer.py`) : remplir le cache à partir de `data/demo/recherches.txt` pour
   le code postal de démo, avec des requêtes modérées.
6. **Jeu de démo** avec le lot 1 : choisir des articles et des magasins bien couverts. Lancer le préchauffage samedi
   matin.

Fin :
- un prix réel en cache s'affiche avec sa date quand la source échoue ;
- Open Prices complète les trous ;
- la recherche d'articles renvoie de vrais produits ;
- le préchauffage fonctionne.

## Fonctionnalités secondaires (bonus, seulement si le MVP est prêt)

| Bonus | Où | Qui (proposition) |
|---|---|---|
| Mode « fin de mois » (équivalents moins chers) | `app/collecte/orchestrateur.py` (`choisir_equivalent`), `app/produits/` | lot 4 |
| Cartes de fidélité, avantages étudiants | `app/panier/calcul.py` (`cartes`), profil dans `app/comptes/` | lots 1 et 2 |
| Trajet (lieux enregistrés, mode de transport, temps estimé) | `app/magasins/trajets.py`, `app/comptes/lieux.py` | fait |
| Répartition sur N magasins | `app/panier/calcul.py` ou nouveau module | lot 1 |

## Jalons (proposition)

| Quand | Objectif |
|---|---|
| Ven. 27/11, 18h | Chacun a cloné, lancé le site et les tests, lu `AGENTS.md`. Fichiers de test enregistrés pour le lot 3 |
| Ven. 27/11, 23h | Premières fusions : parseurs testés (lots 2 et 3), cache (lot 4), interface v2 (lot 1) |
| Sam. 28/11, 9h | Intégration sur `main` : vraies sources activées là où elles marchent, repli ailleurs |
| Sam. 28/11, 11h | Gel des fonctionnalités. Préchauffage du cache, répétition de la démo sur l'ordinateur de démo |
| Sam. 28/11, 13h | Démo |

## Risques

| Risque | Conséquence | Action | Responsable |
|---|---|---|---|
| Clé API Intermarché pas encore approuvée. Produits v1 est marquée « Deprecated », l'accès peut ne jamais être accordé | Pas de prix Intermarché en direct | Vérifier le statut sur le portail ou écrire à ld_red_services@mousquetaires.com. En attendant : aucune requête sans clé, repli (cache, Open Prices) | titulaire du compte du portail (lot 2) |
| Collecte Carrefour, E.Leclerc Drive et Courses U bloquée (403 Cloudflare / DataDome au 27/11) | Pas de prix en direct pour ces enseignes depuis notre serveur | Parseurs testés sur des pages enregistrées, collecte sans contournement, repli sur le cache et Open Prices, préchauffage avant la démo | lots 3 et 4 |
| Open Prices peu fourni autour de Rennes et Bruz. Constaté le 27/11 : presque aucun relevé de moins de 2 ans, aucun lieu à Bruz | Beaucoup de « prix indisponible » quand une enseigne échoue | Le cache des prix réels (préchauffage samedi matin) est le vrai filet. Données fictives marquées en dernier recours. Option : ajouter nous-mêmes des relevés sur Open Prices (application Open Prices, tickets de caisse) | lot 4 |
| Open Food Facts limite les recherches (503) | Recherche d'articles vide | Espacer les appels, cache, catalogue fictif en secours | lot 4 |
| Conflits Git sur les fichiers partagés, et `main` cassée par un push | Perte de temps, démo cassée | Respecter le tableau des fichiers, petits push fréquents, tests verts avant chaque push, `git pull --rebase` avant de pousser | tous |
