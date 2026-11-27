# 2026-11-27 22h45 : adam : documentation remise à jour pour les agents

- **Agent / personne** : Claude Code, session pilotée par Adam
- **Branche** : `main`

## Fait

- `docs/taches.md` réécrit en une page « état actuel » (ce qui marche, ce qui reste avant la démo, qui, jalons,
  risques) : ~960 tokens au lieu de ~3 500. L'ancien découpage en lots reste lisible avec
  `git show f669550:docs/taches.md`.
- `docs/decisions.md` : 13 décisions remplacées ou faites marquées en tête de ligne, avec un renvoi.
- `docs/architecture.md` : organisation du code complétée (drives, tirelire, ticket, listes, vendor), §14 « limites
  connues » remise à jour.
- `AGENTS.md` : note d'état, arborescence (`drives/`, `extensions-edge/`) et règles 3 et 4 alignées sur la nouvelle
  page des tâches.

## Reste à faire

- Chacun met à jour sa ligne de `docs/taches.md` en fin de session.
