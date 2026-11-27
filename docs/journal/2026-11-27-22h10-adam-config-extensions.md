# 2026-11-27 22h10 : adam : configuration des extensions des drives

- **Agent / personne** : Claude Code piloté par Adam
- **Branche** : `main` (non commité)
- **Lot** : aucun (configuration locale)

## Fait

- Création du `.env` local avec un `DRIVES_JETON` aléatoire (fichier ignoré par Git).

## Fichiers modifiés

- `.env` (non versionné) et ce journal.

## Reste à faire

- Relancer le serveur sur `127.0.0.1:8000` pour qu'il lise le jeton.
- Charger les deux extensions dans le navigateur, y saisir le jeton et activer la collecte.
- Essayer une comparaison avec 35170. Jamais vérifié dans Chrome (le guide vise Edge).

## Essai du 27/11 à 22h12

- Serveur relancé, les deux extensions chargées dans Chrome et vues par le serveur.
- Intermarché Bruz Cap Vert : « lait Lactel » réussi, 20 produits relevés.
- Super U Bruz : échec `mauvais_drive` deux fois, y compris après choix du magasin. Cause à confirmer : la
  détection dans `extensions-edge/super-u-bruz/navigation.js` exige une ligne « Super U Bruz » exacte dans un
  `<header>` visible, hors mode livraison.

## Diagnostic Super U (mis de côté à 22h30)

- Échecs `mauvais_drive` après les 18 s de `verifierRetrait` : onglet chargé, bonne adresse, mais `retrait` vide.
- Dans l'onglet de l'extension (en arrière-plan, `document.hidden` vrai), les deux `<header>` ne contiennent aucune
  ligne sur le magasin. Dans l'onglet affiché, « Super U Bruz » y figure.
- Hypothèse non confirmée : le site n'affiche le nom du magasin que dans un onglet visible. Piste : ouvrir ou
  activer l'onglet au premier plan dans `ouvrirOnglet`.
- Journal de diagnostic temporaire retiré de `collecteur.js` (aucune modification de code gardée).
