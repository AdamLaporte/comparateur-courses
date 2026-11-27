# 2026-11-27 21h30 : adam : drives de Bruz dans la comparaison, tirelire en cartes

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `main`
- **Lot** : 1 et intégration du module `drives`

## Fait

- `app/drives/comparaison.py` : associe les magasins du tableau aux drives de Bruz (Super U 33315,
  Intermarché 05052) et donne le prix relevé par l'extension Edge, ou demande une recherche.
- Flux de comparaison (`app/panier/routes.py`) : après les sources habituelles, chaque case sans prix d'un
  drive est cherchée sur le drive ; « Recherche sur le drive… » puis le prix, totaux et verdict mis à jour.
  Nouveau réglage `DRIVES_ATTENTE_S` (75 s). Les articles « inexistant » sont de nouveau comparés.
- Tirelire : cartes à cocher au lieu du menu déroulant.
- Tests : 2 tests des drives dans la comparaison (`tests/test_ticket.py`), test de la tirelire adapté.

## Pour que ça marche en vrai

- `DRIVES_JETON` rempli dans `.env` (le même jeton dans le popup de chaque extension), les extensions de
  `extensions-edge/` installées dans Edge, le site du drive ouvert sur le bon magasin en retrait.
