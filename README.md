# Comparateur de courses

Le site compare les prix d’un panier dans les magasins proches. En mode **Données réelles**, il
affiche les prix enregistrés pour les points de retrait répertoriés et demande à Edge de relever les
prix manquants ou anciens au clic sur **Comparer**. Il peut partir d’une base vide.

## Lancer sous Windows

Depuis PowerShell, à la racine du dépôt, avec [uv](https://docs.astral.sh/uv/) installé.

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Dans `.env`, renseignez `DRIVES_JETON` avec une valeur locale aléatoire. Cette commande en génère une
à copier dans le fichier, puis dans les extensions utilisées. Sur la machine de développement, une valeur a
déjà été générée.

```powershell
[guid]::NewGuid().ToString('N')
```

Lancez le serveur et ouvrez **http://127.0.0.1:8000/** dans Edge.

```powershell
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

## Charger les extensions Edge

Une extension suffit par enseigne. **Comparer** envoie le point de retrait à l’extension, qui
change de magasin dans son onglet puis vérifie le point actif avant d’enregistrer les prix.
Le catalogue initial inclut Super U Bruz, Hyper U Guichen, Intermarché Bruz Cap Vert et Intermarché
Rennes Gayeulles. Les extensions permettent d’ajouter des points de retrait des quatre enseignes
depuis leur catalogue en ligne.

Pour utiliser une seule base depuis plusieurs PC, voir le
[hébergement du site partagé sur un PC avec Tailscale](docs/deploiement-partage.md).

1. Ouvrez `edge://extensions`, activez **Mode développeur**, puis cliquez sur **Charger l’extension non
   empaquetée** pour les enseignes souhaitées. Les dossiers sont `extensions-edge\super-u-bruz`,
   `extensions-edge\intermarche-bruz-cap-vert`, `extensions-edge\carrefour` et
   `extensions-edge\leclerc`. Après une mise à jour, utilisez **Recharger** sur leur carte.
2. Configurez chaque extension une seule fois depuis son popup **Collecte du comparateur**.
   Saisissez le jeton et cliquez sur **Activer la collecte automatique**. Le popup confirme
   **Serveur connecté**. La configuration reste enregistrée au redémarrage d’Edge.
3. Sur Windows, ajoutez `DRIVES_DEMARRER_EDGE=true` dans `.env` et redémarrez le serveur si vous
   souhaitez qu’il ouvre Edge quand le collecteur ne répond pas. Chaque extension ouvre son propre
   onglet marchand quand une demande arrive.
4. Sélectionnez **Données réelles** dans le menu. Depuis l’accueil, saisissez **35170** pour Bruz,
   **35580** pour Guichen ou **35700** pour Rennes Gayeulles. Cliquez sur **Composer ma liste**,
   ajoutez par exemple **lait Lactel**, puis cliquez sur **Comparer**.
   Un nouveau relevé peut attendre jusqu’à 30 secondes avant le prochain réveil de l’extension,
   puis jusqu’à 30 secondes de lecture par article.

Pour un relevé manuel, ouvrez un rayon ou une recherche sur le site marchand, puis cliquez sur
**Relever cette page** dans l’extension. Le panneau indique le point de retrait reconnu et
enregistre les produits avec ce magasin dans le CSV. Le catalogue des magasins est fourni par le
comparateur configuré dans l’extension. Le relevé de Bruz reste disponible hors connexion.

Si Edge est fermé, le comparateur affiche l’historique et indique l’attente du collecteur. La fraîcheur se règle avec
`DRIVES_FRAICHEUR_MIN` dans `.env` (1 440 minutes par défaut). La collecte s’arrête en cas de défi ou
de réponse 403 ou 429 et reprend après la pause de quinze minutes, lors d’une nouvelle recherche.

## Ajouter un point de retrait

1. Choisissez le magasin et le **retrait** sur le site de l’enseigne, puis ouvrez son catalogue
   dans Edge. Pour Carrefour et E.Leclerc Drive, ouvrez un rayon ou cherchez un produit de façon à
   afficher ses prix pour le drive choisi.
   [Courses U](https://www.coursesu.com/drive-france) · [Intermarché](https://www.intermarche.com/enseigne/magazine/tous-les-magasins) · [Carrefour](https://www.carrefour.fr/magasin) · [E.Leclerc Drive](https://www.leclercdrive.fr/)
2. Dans l’extension configurée, ouvrez **Ajouter un magasin au comparateur** puis cliquez sur
   **Détecter le retrait actif**. Vérifiez le nom et complétez l’adresse et le code postal.
   Si l’extension U ou Intermarché demande un lien, collez la page d’accueil Drive ou la page
   **Infos pratiques**, respectivement. Les extensions Carrefour et E.Leclerc déduisent le lien du
   catalogue marchand ouvert.
3. Cliquez sur **Ajouter ce point de retrait**. Le serveur le géolocalise et l’enregistre dans sa
   base. Actualisez le comparateur, cherchez le lieu en mode **Données réelles**, puis lancez
   une comparaison. Le même point de retrait est disponible pour tous les visiteurs du serveur.

Chaque point s’ajoute une fois. L’extension vérifie la référence marchande active avant de relever
les prix. Le point doit proposer le retrait et la recherche de produits en ligne.

## Importer les relevés existants

L’import est facultatif. La base locale de développement a été amorcée avec le relevé Intermarché.
Pour la recréer après avoir extrait le ZIP dans `Downloads`, lancez la commande suivante.

```powershell
$csvIntermarche = Join-Path $env:USERPROFILE 'Downloads\releves_drives_edge_2026-11-27\intermarche_bruz_cap_vert.csv'
uv run --locked python -m app.drives.importer $csvIntermarche
```

Si vous souhaitez ajouter aussi le catalogue Super U, extrait depuis son archive dédiée.

```powershell
$csvSuperU = Join-Path $env:USERPROFILE 'Downloads\super_u_bruz_catalogue_edge_2026-11-27\super_u_bruz_catalogue_2026-11-27.csv'
uv run --locked python -m app.drives.importer $csvSuperU
```

Les observations vont dans la base configurée par `DB_PATH`, soit `data/app.db` par défaut. Le second
import du même fichier ne rajoute aucune observation. Une date sans heure reste affichée comme telle.
Pour la fraîcheur, son âge est calculé depuis le début de cette journée à Paris. Le catalogue Super U
couvre partiellement certains rayons. Pour essayer le démarrage à vide, lancez le serveur avec
`$env:DB_PATH = 'data/drives-vide.db'` dans le même terminal et réservez ce fichier à cet essai.

## Vérifier le projet

```powershell
uv run --locked pytest
uv run --locked ruff format --check .
uv run --locked ruff check .
```

Pour vérifier les extracteurs Edge sur les cartes et pages simulées, lancez le serveur de fichiers
depuis la racine et ouvrez **http://127.0.0.1:8765/tests/donnees/drives/navigateur.html** dans Edge.
La page affiche `DRIVES_BROWSER_OK` lorsque les contrôles passent.
Le test `/tests/donnees/drives/collecteur.html` vérifie aussi l’ouverture automatique d’un onglet
et l’arrêt sur défi simulé. Il affiche `DRIVES_COLLECTEUR_OK`.

```powershell
uv run --locked python -m http.server 8765 --bind 127.0.0.1
```

Les scénarios locaux couvrent les changements de drive et les refus de prix d’un autre magasin.
L’ajout et le premier relevé en conditions réelles restent à vérifier sur le poste de collecte
pour Carrefour et E.Leclerc.
