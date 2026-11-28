# 2026-11-28 : adam : retrait de l’ajout de magasins, comparaison sur clic, correctifs

- **Agent / personne** : Claude Code piloté par Adam
- **Branche** : `main`
- **Tâche** : correctifs avant la démo

## Fait

- Retiré l’ajout de points de retrait depuis les extensions (serveur, quatre popups, détection, tests).
- La comparaison ne part plus seule (`?comparer=1` sans effet) et la page ne redescend plus à chaque prix reçu
  (attribut `hx-swap` hérité par les cases SSE). Ajouter un article ne déplace pas la page.
- Corrigé : une tâche d’un point non répertorié pouvait faire planter la prise de tâche de l’enseigne.
- Corrigé : un relevé récent citant seulement le mot (« sans lait ») empêchait de chercher « lait » sur le drive.
- Vérifié : pytest, ruff, simulations Edge (extracteurs, collecteur, relevé manuel, ouverture des quatre popups),
  parcours dans Chrome sur une copie de la base (aucun défilement automatique en démo ni en données réelles).

## Fichiers modifiés

- `app/drives/`, `app/magasins/`, `app/collecte/`, `app/panier/routes.py`, `app/acces_partage.py`,
  `app/mode_donnees.py`, `app/static/site.js`, gabarits `panier/page.html` et `magasins/`.
- `extensions-edge/` (quatre extensions), `tests/`, `README.md`, `docs/`.

## Reste à faire

- Recharger les extensions dans `edge://extensions` et faire un relevé réel par enseigne.
- Redémarrer l’instance partagée après `git pull`.

## Points d’attention pour la suite

- Les extensions traitent une tâche par réveil (30 s) et par enseigne : en données réelles, une longue liste dépasse
  `DRIVES_ATTENTE_S` (75 s) à la première comparaison. Préchauffer les articles de la démo.
- « lait » peut encore retenir « laitue » (le sujet est comparé par début de mot). Non modifié.
- Après le push, chacun fait `git pull --rebase` avant de reprendre.
