# Tâches : état actuel

> À lire avant de commencer (règle n°1 d'`AGENTS.md`). Une page courte : ce qui marche, ce qui reste avant la
> démo, qui s'en occupe. Mettez-la à jour à la fin de votre session (statut + une ligne au plus par tâche).
> L'ancien découpage en 4 lots (cadrage du 27/11 après-midi) est dans l'historique Git : `git show f669550:docs/taches.md`.

**Démo : samedi 28 novembre 2026, 13h.** Gel des fonctionnalités à 11h. Mis à jour le 28/11.

## Comment travailler

1. `git pull --rebase`, `uv sync`, `cp .env.example .env` la première fois, puis
   `uv run uvicorn app.main:app --reload` → http://localhost:8000.
2. Une seule branche : `main`. Petits commits ; avant `git push` : `uv run pytest`, `uv run ruff check .`,
   `git pull --rebase`.
3. Lire `docs/architecture.md` avant de changer la structure ; une ligne dans `docs/decisions.md` par décision ;
   un journal par session dans `docs/journal/`.

## Ce qui marche (sur `main`)

| Partie | État | Qui |
|---|---|---|
| Magasins | 9 324 magasins réels (OpenStreetMap), ville, code postal ou « Me localiser », rayon, carte | Adam |
| Lieux et trajets | Lieux enregistrés, mode favori, rayon adapté et estimation de trajet à la demande | Ilona |
| Ma liste | Recherche Open Food Facts, produit précis ou « le moins cher », quantités, vider et annuler, listes nommées, favoris | Adam, Ilona, Jade |
| Ticket de caisse | Photo lue par OCR local, articles rapprochés du catalogue, « inexistant » sinon | Adam |
| Comparaison | Prix en direct (SSE), verdict (même sans panier complet), classement, prix périmés signalés | Adam |
| Prix réels | Cache, Open Prices et relevés Edge. Carrefour Drive Chartres-de-Bretagne et E.Leclerc Drive Bruz – Ker Lann sont proposés par le catalogue autour de Bruz | Jade, Raph |
| Mode des données | Bouton dans le menu pour passer de prix fictifs sans Edge aux relevés réels des points connus ou ajoutés. Défaut `MODE_DONNEES_DEFAUT` | Jade |
| Site partagé | Base commune sur le PC de Raph via Tailscale, avec accès privé et jetons de collecte. Réutilisation réelle sur le second PC à valider | Raph, Adam |
| Comptes | Inscription, connexion, mot de passe perdu, maison, favoris, tirelire (écart avec la moyenne) | Jade, Ilona |
| Interface | GrignotePrix (nom, logo, couleurs), animations, mobile, fonctionne sans Internet (sauf fonds de carte) | Adam, Ilona |

Les prix des magasins hors catalogue de retrait restent fictifs ou viennent
d'Open Prices : la collecte directe de ces sites est abandonnée (403 Cloudflare / DataDome).

## Ce qui reste avant la démo

| Tâche | Qui | Statut |
|---|---|---|
| Préparer les prix réels autour de Bruz | Raph | 190 relevés Carrefour Chartres-de-Bretagne et 105 relevés E.Leclerc Ker Lann importés sur les deux instances. Lait, pâtes et riz vérifiés dans la base partagée |
| Valider un relevé réel avec les deux extensions sur l'ordinateur de démo (`DRIVES_JETON` identique dans `.env` et les popups) | Raph | Intermarché réussi le 27/11 à 22h12 |
| Scénario de démo : lieu (Bruz), 6 à 8 articles bien couverts, ordre de ce qu'on montre | Adam, Jade | à faire |
| Préchauffage du cache sur ces articles (`uv run python -m app.collecte.prechauffer data/demo/recherches.txt --code-postal 35170`) samedi matin | Jade | à faire |
| Répétition complète sur l'ordinateur de démo (serveur lancé, extensions actives, compte de démo connecté) | tous | samedi 11h |
| Mise en ligne (Render) : facultatif, seulement si tout le reste est prêt | Adam | facultatif |

## Jalons

| Quand | Objectif |
|---|---|
| Sam. 28/11, 9h | Tout est sur `main`, tests verts ; extensions validées sur l'ordinateur de démo |
| Sam. 28/11, 11h | Gel des fonctionnalités, préchauffage, répétition |
| Sam. 28/11, 13h | Démo |

## Risques

| Risque | Parade |
|---|---|
| Une extension ne relève pas pendant la démo (défi anti-robots, mauvais drive, pas de réseau) | Préchauffer la veille : les prix récents restent affichés avec leur date ; sinon cache et Open Prices |
| Peu de prix réels hors Bruz | Faire la démo à Bruz (35170) avec les articles préchauffés ; les prix fictifs restent marqués |
| Conflits Git de dernière minute | Petits commits, `git pull --rebase` avant chaque push, gel à 11h |
