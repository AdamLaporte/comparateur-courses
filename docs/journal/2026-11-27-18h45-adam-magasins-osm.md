# 2026-11-27 18h45 : adam : magasins OpenStreetMap, ville, position et rayon

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `main`
- **Lot** : 2 (partie magasins)

## Fait

- Tous les magasins Carrefour, Intermarché, U et E.Leclerc de France (9 324) téléchargés une fois depuis
  OpenStreetMap (Overpass) dans `data/magasins/osm.json`. Script de mise à jour : `uv run python -m app.magasins.import_osm`.
- Recherche par ville, code postal ou position du navigateur (bouton « Me localiser »).
- Choix : « les plus proches de chaque enseigne » ou « dans un rayon de 2, 5, 10, 20 ou 30 km ». Le rayon est gardé
  en session et utilisé par la liste et la comparaison.
- Mention « © contributeurs OpenStreetMap (ODbL) » sous la liste.
- Tests : `tests/test_magasins.py` (6 tests, sans réseau). 53 tests verts.

## Fichiers modifiés

- `app/magasins/` (service, geocodage, routes, nouveau `import_osm.py`), `app/panier/routes.py` (rayon de session)
- Ajouts partagés : `app/config.py` (`magasins_osm`, `max_magasins_par_enseigne_rayon`), `app/contrats.py`
  (`MagasinsReponse.rayon_km`), `.env.example`
- `app/templates/magasins/*`, `app/templates/panier/page.html`, `app/static/style.css`
- `tests/conftest.py` (`magasins_osm=False`), `tests/test_parcours.py`, `tests/test_magasins.py`
- `data/magasins/osm.json`, docs

## Reste à faire

- Les prix restent fictifs pour ces vrais magasins. Une vraie source (scraping, cache) devra faire le lien entre
  l'identifiant OSM (`carrefour-osmn123`) et l'identifiant du magasin chez l'enseigne.
- 75 % des magasins OSM n'ont pas d'adresse : seuls le nom et la distance s'affichent.
- Les drives E.Leclerc séparés sont rarement dans OSM : on montre le magasin E.Leclerc.
