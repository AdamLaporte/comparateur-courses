# Héberger le comparateur partagé sur un PC Windows

Les deux PC ouvrent le même site HTTPS via Tailscale. Le PC de Raphaël garde la base commune
dans `data/partage/app.db`. Le site partagé est disponible lorsque ce PC est allumé, connecté à
Tailscale et que le serveur du comparateur tourne.

## Démarrer le site

1. Installez Tailscale sur les deux PC. Sur le PC hôte, connectez-vous à Tailscale, puis invitez
   Adam dans le réseau privé ou partagez-lui uniquement ce PC. Sur son PC, Adam accepte
   l’invitation et se connecte sous son propre compte. [Partager une machine](https://tailscale.com/kb/1084/sharing)
2. Sur le PC hôte, ouvrez PowerShell et démarrez **Tailscale Serve**. Si Tailscale demande
   d’activer les certificats HTTPS, ouvrez le lien indiqué et validez la configuration.
   Tailscale affiche une adresse en `.ts.net`. [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)

```powershell
tailscale serve --bg http://127.0.0.1:8001
```

3. Dans la racine du dépôt, lancez le serveur en remplaçant l’adresse d’exemple par l’adresse
   obtenue. Gardez le serveur en fonctionnement pendant le partage.

```powershell
uv sync --locked
uv run --locked python -m app.site_partage https://nom-du-pc.nom-du-reseau.ts.net
```

La première exécution génère `.env.partage` avec deux comptes Web, deux jetons Edge et une
clé de session. Ce fichier reste sur le PC hôte, hors de Git. La base commune démarre vide.
Au redémarrage du comparateur, relancez la même commande pour retrouver les prix et les accès.
La configuration Tailscale Serve en arrière-plan persiste. Le site local sur le port 8000
continue d’utiliser sa propre base.

## Connecter les deux PC

- Ouvrez l’adresse HTTPS Tailscale dans chaque navigateur. Dans `.env.partage`, la variable
  `SITE_PARTAGE_COMPTES` contient les identifiants `raphael` et `adam` et leurs mots de passe.
  Donnez à Adam uniquement son mot de passe et son jeton, via un canal privé.
- Chargez ou rechargez les [extensions Edge des enseignes souhaitées](../README.md#charger-les-extensions-edge)
  sur chaque poste qui collecte. Chaque extension traite les points répertoriés pour son enseigne.
  Dans **Collecte du comparateur**, entrez l’adresse HTTPS et votre jeton de `DRIVES_COLLECTEURS`
  (`edge-raphael` ou `edge-adam`). Cliquez sur **Activer la collecte automatique** et autorisez
  l’accès à l’adresse. Le popup doit afficher **Serveur connecté**.
- Pour révoquer un jeton, supprimez son entrée dans `DRIVES_COLLECTEURS` et relancez le site.

## Vérifier le partage

1. Raphaël compare **Nutella** autour de **35170** et attend le relevé Intermarché.
2. Adam ouvre la même adresse et refait la comparaison avec son extension suspendue. Le même
   prix daté doit s’afficher, avec son propre panier. Une demande en file reste récupérable
   pendant 24 h. Les prix connus restent lisibles si le navigateur collecteur est fermé.
3. Relancez le serveur et vérifiez que le prix est toujours présent. Pour sauvegarder la base,
   utilisez l’API de sauvegarde SQLite ou arrêtez le serveur avant de copier le fichier.
