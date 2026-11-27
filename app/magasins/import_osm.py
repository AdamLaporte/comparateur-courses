"""Télécharge tous les magasins des 4 enseignes en France depuis OpenStreetMap (API Overpass, gratuite,
sans clé) et les enregistre dans data/magasins/osm.json. À relancer de temps en temps, pas à chaque
recherche : Overpass met environ 2 minutes et refuse souvent les requêtes quand il est saturé.

    uv run python -m app.magasins.import_osm                 # télécharge puis enregistre
    uv run python -m app.magasins.import_osm brut.json       # part d'une réponse déjà téléchargée

Données © contributeurs OpenStreetMap, licence ODbL : la mention est affichée sous la liste des magasins.
"""

import json
import sys
from pathlib import Path

import httpx

from app.config import Reglages
from app.contrats import Enseigne

FICHIER = Path(__file__).resolve().parents[2] / "data" / "magasins" / "osm.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUETE = (
    '[out:json][timeout:300];area["ISO3166-1"="FR"][admin_level=2]->.fr;'
    'nwr["shop"~"^(supermarket|convenience)$"]'
    '["brand"~"carrefour|intermarch|leclerc|^super u$|^hyper u$|^u express$|^utile$",i](area.fr);'
    "out center tags;"
)
MARQUES_U = {"super u", "hyper u", "u express", "utile"}


def enseigne_de(marque: str) -> Enseigne | None:
    m = marque.lower()
    if "leclerc" in m:
        return Enseigne.LECLERC
    if "intermarch" in m:
        return Enseigne.INTERMARCHE
    if "carrefour" in m:
        return Enseigne.CARREFOUR
    if m in MARQUES_U:
        return Enseigne.COURSES_U
    return None


def compacter(elements: list[dict]) -> list[dict]:
    magasins = []
    for e in elements:
        tags = e.get("tags", {})
        enseigne = enseigne_de(tags.get("brand", ""))
        point = e if "lat" in e else e.get("center")
        if enseigne is None or not point:
            continue
        rue = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
        magasins.append(
            {
                "id": f"{e['type'][0]}{e['id']}",
                "enseigne": enseigne.value,
                "nom": tags.get("name") or tags.get("brand"),
                "adresse": rue,
                "code_postal": tags.get("addr:postcode", ""),
                "ville": tags.get("addr:city", ""),
                "lat": round(point["lat"], 6),
                "lon": round(point["lon"], 6),
            }
        )
    return magasins


def main() -> None:
    if len(sys.argv) > 1:
        elements = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["elements"]
    else:
        reponse = httpx.post(
            OVERPASS_URL,
            data={"data": REQUETE},
            headers={"User-Agent": Reglages().user_agent_services},
            timeout=330,
        )
        reponse.raise_for_status()
        elements = reponse.json()["elements"]
    magasins = compacter(elements)
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(
        json.dumps(magasins, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"{len(magasins)} magasins enregistrés dans {FICHIER}")


if __name__ == "__main__":
    main()
