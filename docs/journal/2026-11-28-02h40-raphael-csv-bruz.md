# 2026-11-28 02h40 — Raphaël — relevés CSV autour de Bruz

- **Agent / personne** — Codex, piloté par Raphaël.
- **Branche** — `main`.
- **Lot** — démo avec prix marchands autour de Bruz.

## Fait

- Importé dans les bases locale et partagée 190 observations de `carrefour_chartres.csv` du 27/11 et 105 observations issues de `leclerc_bruz_ker_lann.csv` du 27/11 et `leclerc-bruz-ker-lann_2026-11-28.csv`. Les fichiers originaux restent dans Téléchargements et leurs dates ont été conservées.
- Associé les lignes Carrefour au point Chartres-de-Bretagne et les lignes E.Leclerc au point Ker Lann après vérification de leurs libellés et liens marchands.
- Enregistré dans le catalogue et les deux bases l’adresse E.Leclerc `https://fd6-courses.leclercdrive.fr/magasin-113511-113511-bruz---ker-lann.aspx` confirmée par le dernier CSV. Vérifié le lien et les relevés « lait », « pâtes » et « riz » via le serveur partagé.

## Fichiers modifiés

- `app/drives/points_retrait.json`, `app/drives/modeles.py`, `tests/donnees/drives/collecteur.html` et documentation de suivi.
- `data/app.db` et `data/partage/app.db` pour les observations locales.

## Reste à faire

- Un nouveau CSV Carrefour daté du 28/11 et un relevé de Carré Frais ne sont pas présents dans les fichiers vérifiés. La démo utilise les produits couverts par les CSV existants.
