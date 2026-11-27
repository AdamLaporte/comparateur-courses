# Tâches

> À lire avant de commencer (règle n°1 d'`AGENTS.md`). Chacun tient à jour le statut de son lot.
> Statuts : `à faire`, `en cours`, `en attente de validation`, `fait`, `bloqué`.

## Mise en place (Claude Code)

| Étape | Contenu | Statut |
|---|---|---|
| 1. Cadrage | Questions, recherches sur les sources, choix de l'architecture A | fait |
| 2. Conception | `docs/architecture.md` (3 diagrammes), `AGENTS.md`, `CLAUDE.md`, `docs/decisions.md`, ce fichier, journal | en attente de validation |
| 3. Squelette | Projet uv, configuration, parcours de bout en bout avec données fictives (code postal → magasins → liste → total par magasin), tests | à faire |
| 4. Répartition | 4 lots indépendants dans ce fichier, attribution des personnes | à faire |

## Lots

Le découpage détaillé sera écrit à l'étape 4. Grandes lignes prévues :

| Lot | Contenu | Qui | Statut |
|---|---|---|---|
| 1. Interface | Templates HTMX, tableau des prix en SSE, affichage source et heure, rendu pour la démo, écrans des comptes | à attribuer | à faire |
| 2. Intermarché, magasins et comptes | D'abord ce qui marche sans clé (lecture des réponses à partir des exemples des specs OpenAPI, tests, liste fixe des magasins Rennes/Bruz ou Open Prices), puis appels réels quand la clé arrive. Géocodage par l'API Adresse. Comptes et favoris | à attribuer | à faire |
| 3. Collecte web (Codex) | 3a Carrefour (lecture de `routeData`), 3b E.Leclerc Drive, 3c Courses U, en sous-lots indépendants | à attribuer | à faire |
| 4. Données et fiabilité | Cache SQLite, repli, Open Prices, référentiel Open Food Facts, règles d'équivalence, commande de préchauffage | à attribuer | à faire |

## Risques

| Risque | Conséquence | Action | Responsable |
|---|---|---|---|
| Clé API Intermarché pas encore approuvée. Produits v1 est marquée « Deprecated », l'accès peut ne jamais être accordé | Pas de prix Intermarché en direct | Vérifier le statut sur le portail ou écrire à ld_red_services@mousquetaires.com. En attendant : aucune requête sans clé, repli (cache, Open Prices) | titulaire du compte du portail |
| Collecte Carrefour, E.Leclerc Drive et Courses U bloquée (403 Cloudflare / DataDome au 27/11) | Pas de prix en direct pour ces enseignes depuis notre serveur | Implémenter la collecte (lot 3), sans contournement. Repli sur le cache et Open Prices. Préchauffer le cache avant la démo | lot 3 et lot 4 |
| Open Prices peu fourni autour de Rennes et Bruz | Beaucoup de « prix indisponible » | Choisir pour la démo des articles et des magasins bien couverts. Données fictives marquées en dernier recours | lot 4 |
