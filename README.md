# Comparateur de courses

Le site compare des prix par article ou par panier. Le parcours **Drives de Bruz** compare les prix
de retrait de Super U Bruz et d’Intermarché Bruz Cap Vert. Il peut partir d’une base vide.

## Lancer sous Windows

Depuis PowerShell, à la racine du dépôt, avec [uv](https://docs.astral.sh/uv/) installé.

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Dans `.env`, renseignez `DRIVES_JETON` avec une valeur locale aléatoire. Cette commande en génère une
à copier dans le fichier, puis dans les deux extensions. Sur la machine de développement, une valeur a
déjà été générée.

```powershell
[guid]::NewGuid().ToString('N')
```

Lancez le serveur et ouvrez **http://127.0.0.1:8000/drives** dans Edge.

```powershell
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

## Charger les extensions Edge

1. Ouvrez `edge://extensions`, activez **Mode développeur**, puis cliquez sur **Charger l’extension non
   empaquetée** pour chacun des dossiers `extensions-edge\super-u-bruz` et
   `extensions-edge\intermarche-bruz-cap-vert`. Après une mise à jour, utilisez **Recharger** sur
   chaque carte d’extension.
2. Dans deux onglets, ouvrez les sites marchands et sélectionnez le retrait indiqué. Pour Intermarché,
   vérifiez **Cap Vert, 2 place Robert Barré**. Pour Super U, vérifiez **12 place de Bretagne**.
3. Dans chaque onglet marchand, ouvrez l’extension correspondante, puis **Collecte du comparateur local**.
   Saisissez le jeton, cliquez sur **Utiliser cet onglet pour la collecte** et gardez l’onglet ouvert
   sur le site. Répétez la sélection de l’onglet après un redémarrage d’Edge.
4. Sur la page du comparateur, cochez les deux drives et cherchez par exemple **lait Lactel**. Les prix
   connus s’affichent tout de suite. Pour un nouveau relevé, comptez jusqu’à 30 secondes avant le prochain
   réveil de l’extension, puis jusqu’à 30 secondes de lecture. Relancez la recherche pour voir la
   réutilisation des résultats.

Le relevé manuel et l’export CSV restent accessibles dans les deux extensions. Si Edge est fermé, le
comparateur affiche l’historique et indique l’attente du collecteur. La fraîcheur se règle avec
`DRIVES_FRAICHEUR_MIN` dans `.env` (1 440 minutes par défaut). La collecte s’arrête en cas de défi ou
de réponse 403 ou 429 et reprend après la pause de quinze minutes, lors d’une nouvelle recherche.

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

```powershell
uv run --locked python -m http.server 8765 --bind 127.0.0.1
```

Les sites ont présenté des défis dans la session Edge isolée utilisée pour la vérification. Le
fonctionnement des recherches marchandes en conditions réelles reste à confirmer dans la session Edge
utilisateur, notamment le formulaire de Super U, l’état sans résultat des deux sites et l’identité du
retrait sur la page de résultats.
