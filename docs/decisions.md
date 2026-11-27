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
| 2026-11-27 | Journal des sessions d'agent : `prenom` = prénom de la personne qui pilote l'agent, ou `claude` / `codex` s'il n'est pas connu | Savoir qui a fait quoi |
