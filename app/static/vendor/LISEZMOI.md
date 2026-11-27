# Bibliothèques et polices copiées dans le projet

Copiées le 27/11/2026 depuis jsdelivr pour que le site marche sans Internet (démo). Ne pas les modifier : pour
changer de version, retélécharger le fichier et mettre à jour ce tableau et les gabarits.

| Fichier | Source | Licence |
|---|---|---|
| `htmx-2.0.4.min.js` | `htmx.org@2.0.4/dist/htmx.min.js` (empreinte SRI officielle vérifiée) | 0BSD (`LICENCE-htmx.txt`) |
| `htmx-ext-sse-2.2.2.js` | `htmx-ext-sse@2.2.2/sse.js` | 0BSD, comme htmx |
| `leaflet-1.9.4/leaflet.js`, `leaflet.css` | `leaflet@1.9.4/dist/` | BSD-2-Clause (`leaflet-1.9.4/LICENSE`) |
| `polices/archivo-*-wdth-normal.woff2` | `@fontsource-variable/archivo@5.3.0/files/` (latin, latin-ext) | SIL OFL 1.1 (`polices/LICENCE-archivo.txt`) |
| `polices/ibm-plex-mono-*-{400,500}-normal.woff2` | `@fontsource/ibm-plex-mono@5.3.0/files/` (latin, latin-ext) | SIL OFL 1.1 (`polices/LICENCE-ibm-plex-mono.txt`) |

Les `@font-face` sont en tête de `app/static/style.css`. Seuls les fonds de carte (tuiles OpenStreetMap) restent
chargés depuis Internet : sans réseau, la carte reste grise mais la liste des magasins suffit.
