# 2026-11-27 : jade : mode des données (démo / réelles)

- **Agent / personne** : Claude Code piloté par Jade
- **Branche** : `main`
- **Tâche** : interrupteur « démo » / « données réelles » sur le site

## Fait

- Bouton dans le bandeau, choix gardé dans la session de chaque visiteur, défaut `MODE_DONNEES_DEFAUT=demo`.
- Mode démo : tous les magasins, prix fictifs (drives compris), **aucune requête aux extensions Edge**.
- Mode réel : **seulement les drives répertoriés** (Super U et Intermarché de Bruz, Hyper U Guichen,
  Intermarché Rennes Gayeulles), prix relevés par les extensions, **rien de fictif**. Le bandeau signale si la
  collecte Edge n'est pas configurée (`DRIVES_JETON`).
- Même mode pour la page des magasins, le tableau et le flux SSE (mêmes magasins partout).
- Tests : `tests/test_mode_donnees.py` (6 tests). Les tests Edge existants (drives, ticket, site partagé) se lancent
  en mode réel ; ceux qui vérifient Bruz seul prennent un rayon de 5 km (en mode réel, Guichen et Rennes entrent
  dans le rayon par défaut).
- Vérifié dans le navigateur : 8 magasins en démo, 4 drives en mode réel.

## Fichiers modifiés

- Nouveau : `app/mode_donnees.py`, `tests/test_mode_donnees.py`
- Partagés (commit à part) : `app/config.py`, `.env.example`, `app/main.py`, `app/templates/base.html`
- `app/magasins/service.py` (`seulement_drives`), `app/magasins/routes.py`, `app/collecte/orchestrateur.py`
  (`drives_par_edge`), `app/panier/routes.py`, `app/static/style.css`
- Tests ajustés : `tests/test_drives.py`, `tests/test_ticket.py`, `tests/test_site_partage.py`, `tests/test_parcours.py`
- `docs/architecture.md` (§17), `docs/decisions.md`, `docs/taches.md`

## Reste à faire

- Le jour de la démo : choisir le mode dans le bandeau (ou `MODE_DONNEES_DEFAUT=reel` dans `.env` de l'ordinateur de
  démo si les extensions marchent).

## Points d'attention pour la suite

- L'API JSON sans session (`/api/panier/totaux`, `/api/magasins`) reste en mode démo.
- En mode réel, sans drive répertorié dans le rayon (ex. Paris), la liste des magasins est vide : c'est voulu.
