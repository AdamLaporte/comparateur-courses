# Décisions

Une ligne par décision importante, la plus récente en bas. Toute modification d'un fichier partagé
(`app/main.py`, `app/config.py`, `app/db.py`, `app/contrats.py`, `app/sources/base.py`, `app/templates/base.html`)
est aussi notée ici.

| Date | Décision | Raison |
|---|---|---|
| 2026-11-27 | Architecture A : un seul FastAPI, pages Jinja2 + HTMX, prix et totaux en direct par SSE, API JSON `/api/...` avec les mêmes schémas | Choix de l'équipe. Tout en Python, parcours complet le plus rapide, fichiers séparés pour 4 personnes. B (React) coûte 2 à 3 h, C (Streamlit) gère mal l'asynchrone, les comptes et les tests |
| 2026-11-27 | Une seule interface `SourcePrix` (`trouver_magasins`, `chercher_produits`, `obtenir_prix`) pour toutes les sources | Le reste de l'application ne dépend que d'elle. Une source = un fichier = un lot |
| 2026-11-27 | Chaque ligne de liste est au choix un produit précis (EAN) ou « le moins cher équivalent » (recherche texte) | Choix de l'équipe. Les marques distributeur n'existent que dans leur enseigne |
| 2026-11-27 | Collecte Carrefour, E.Leclerc Drive et Courses U conçue comme le cahier des charges, mais implémentée plus tard (Codex) | Choix de l'équipe. Test du 27/11 : curl reçoit 403 Cloudflare `cf-mitigated: challenge` (carrefour.fr, coursesu.com) et DataDome (leclercdrive.fr). On ne contourne pas |
| 2026-11-27 | Repli en cas d'échec : dernier prix en cache avec sa date, puis Open Prices, puis « prix indisponible » | Cahier des charges. Jamais d'erreur brute à l'utilisateur |
| 2026-11-27 | Intermarché : pas de clé d'API (demande pas encore approuvée). `INTERMARCHE_API_KEY` vide dans `.env.example`. Sans clé, la source n'envoie aucune requête et passe directement au repli (cache, Open Prices, indisponible) | Correction de l'équipe. Inutile d'appeler une API qui refusera |
| 2026-11-27 | Magasins Intermarché sans clé : liste fixe pour la zone de démo (Rennes, Bruz) ou magasins Intermarché connus d'Open Prices | L'API Stores exige la clé |
| 2026-11-27 | Risque : Produits v1 est marquée « Deprecated », l'accès peut ne jamais être accordé. Le ou la titulaire du compte vérifie le statut sur le portail ou écrit à ld_red_services@mousquetaires.com | Portail développeurs lu le 27/11 |
| 2026-11-27 | Le lot Intermarché commence par ce qui marche sans clé : lecture des réponses à partir des exemples des specs OpenAPI, avec tests | Avancer sans attendre la clé |
| 2026-11-27 | Démo en local (`uv run`), Dockerfile minimal préparé, mise en ligne seulement s'il reste du temps samedi matin | Choix de l'équipe. Moins de risque la nuit |
| 2026-11-27 | SQLite via le module `sqlite3`, sans ORM, chaque fonctionnalité déclare ses tables dans son module | Simple, et pas de fichier de schéma commun que tout le monde modifierait |
| 2026-11-27 | Montants en centimes entiers | Pas d'erreurs d'arrondi des nombres à virgule |
| 2026-11-27 | `Prix.prix_centimes` = prix en caisse sans condition (promo immédiate déjà déduite). Promos « lot » déduites selon la quantité. Promos fidélité stockées mais non déduites tant que la carte n'est pas déclarée | Total honnête pour tous, et prépare la fonctionnalité « long terme » |
| 2026-11-27 | Python 3.13 installé par uv | Bien supporté par toutes les dépendances, uv l'installe tout seul sur chaque machine |
| 2026-11-27 | Géocodage du code postal : table intégrée (35170 Bruz, 35000 Rennes…), puis API Adresse de la Géoplateforme | Démo possible sans réseau pour la zone de démo, API gratuite et sans clé |
| 2026-11-27 | Session par cookie signé. Sans compte, la liste est liée à la session. Avec un compte, à l'utilisateur. Mots de passe hachés en argon2 (`pwdlib`) | Tout est utilisable sans compte |
| 2026-11-27 | `app/main.py` inclut tous les routers et `app/config.py` déclare tous les réglages dès le squelette. `contrats.py` et `sources/base.py` ne changent qu'en concertation | Éviter les conflits Git avec 4 humains et plusieurs agents |
| 2026-11-27 | Identifiant de magasin `"<enseigne>-<id_enseigne>"` | Utilisable tel quel dans les identifiants HTML et les noms d'événements SSE |
| 2026-11-27 | HTMX et son extension SSE chargés depuis un CDN | Rien à compiler. Internet est de toute façon nécessaire pendant la démo pour les prix |
| 2026-11-27 | Adam (GitHub `AdamLaporte`) est responsable du dépôt Git : dépôt distant, ajout des participants, fusions et envois. Sur son poste, les commits sont signés « Adam Laporte » avec son adresse noreply GitHub | Demande d'Adam. Commits rattachés à son compte sans exposer d'e-mail personnel |
| 2026-11-27 | Journal des sessions d'agent : `prenom` = prénom de la personne qui pilote l'agent, ou `claude` / `codex` s'il n'est pas connu | Savoir qui a fait quoi |
| 2026-11-27 | SSE avec le support intégré à FastAPI (`fastapi.sse`, version 0.165) au lieu de `sse-starlette` | Même service avec une dépendance de moins |
| 2026-11-27 | Dépendance `tzdata` ajoutée | L'heure de Paris s'affiche aussi sous Windows, où le système ne fournit pas les fuseaux |
| 2026-11-27 | Tables déclarées dans `app/<fonctionnalite>/schema.sql`, toutes exécutées au démarrage par `app/db.py` | Ajouter une table ne touche aucun fichier partagé |
| 2026-11-27 | Nouveau fichier partagé `app/gabarits.py` (Jinja2 commun, filtres `euros` et `releve`, `rendre()` pour les fragments SSE) | Un seul moteur de templates pour les pages et les fragments envoyés par SSE |
| 2026-11-27 | Dépendance FastAPI des réglages : `reglages: ReglagesDep` (`Annotated`), réglages portés par `app.state` | Forme recommandée par FastAPI, et les tests créent l'application avec leurs propres réglages (`creer_app(reglages)`) |
| 2026-11-27 | ruff : règle E501 (longueur des lignes) ignorée, `ruff format` gère la longueur du code | Les docstrings et commentaires en français dépassent souvent 100 caractères |
| 2026-11-27 | Mode « équivalent » : on retient l'offre la moins chère au prix unitaire (au kilo, au litre) si toutes les offres l'ont, sinon au prix | Règle simple et défendable. Le lot 4 pourra l'affiner (mode fin de mois) |
| 2026-11-27 | Données fictives : 5 vrais EAN (Nutella, Coca-Cola, Uncle Ben's, Carte Noire, lait Carrefour Classic') et des EAN fictifs commençant par 2 (plage réservée à l'usage interne), avec des marques inventées | Pas de fausses associations entre un vrai code-barres et un faux produit |
| 2026-11-27 | La source fictive donne un prix générique à tout EAN hors catalogue | Le parcours marche aussi avec des produits venus d'Open Food Facts quand le lot 4 les branchera |
| 2026-11-27 | Événement SSE `fin` + `sse-close="fin"` côté HTMX | Sans cela, le navigateur se reconnecte et relance toute la collecte |
