"""Magasins proches : lieu → position → magasins des 4 enseignes triés par distance.

Deux modes de recherche :
- rayon_km=None : les plus proches de chaque enseigne (MAX_MAGASINS_PAR_ENSEIGNE, jusqu'à 50 km) ;
- rayon_km=N : tous les magasins à moins de N km (au plus MAX_MAGASINS_PAR_ENSEIGNE_RAYON par enseigne).

Les magasins viennent de data/magasins/osm.json (OpenStreetMap, voir import_osm.py) si MAGASINS_OSM est
vrai et que le fichier existe ; sinon de trouver_magasins() de chaque source (magasins fictifs).
"""

import asyncio
import json
import logging
import math
from collections.abc import Iterable
from functools import cache
from itertools import chain

from app.config import Reglages
from app.contrats import Enseigne, Magasin, MagasinsReponse, Position
from app.drives.catalogue import magasin_retrait, magasins_inscrits
from app.drives.modeles import DRIVES, DRIVES_OSM
from app.magasins.geocodage import geocoder
from app.magasins.import_osm import FICHIER as FICHIER_OSM
from app.sources.base import SourceIndisponible, SourcePrix
from app.sources.registre import sources_actives

logger = logging.getLogger(__name__)

RAYON_PLUS_PROCHES_KM = 50.0


def distance_km(a: Position, b: Position) -> float:
    """Distance à vol d'oiseau (formule de haversine)."""
    rayon_terre = 6371.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = phi2 - phi1
    dlambda = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * rayon_terre * math.asin(math.sqrt(min(1.0, h)))


def _limites(rayon_km: float | None, reglages: Reglages) -> tuple[float, int]:
    if rayon_km is None:
        return RAYON_PLUS_PROCHES_KM, reglages.max_magasins_par_enseigne
    return rayon_km, reglages.max_magasins_par_enseigne_rayon


def _garder_proches(
    magasins: Iterable[Magasin], position: Position, rayon: float, maximum: int
) -> list[Magasin]:
    proches = []
    for magasin in magasins:
        distance = distance_km(position, magasin.position)
        if distance <= rayon:
            proches.append(magasin.model_copy(update={"distance_km": round(distance, 1)}))
    proches.sort(key=lambda m: m.distance_km)
    return proches[:maximum]


def _magasins_initiaux() -> Iterable[Magasin]:
    for drive, point in DRIVES.items():
        if point.coordonnees is not None:
            yield magasin_retrait(drive, point, point.coordonnees)


@cache
def magasins_osm() -> dict[Enseigne, list[Magasin]]:
    """Magasins OpenStreetMap et points de retrait du catalogue initial, par enseigne."""
    par_enseigne: dict[Enseigne, list[Magasin]] = {e: [] for e in Enseigne}
    drives_associes = set()
    for m in json.loads(FICHIER_OSM.read_text(encoding="utf-8")):
        enseigne = Enseigne(m["enseigne"])
        if drive_id := DRIVES_OSM.get(m["id"]):
            point = DRIVES[drive_id]
            drives_associes.add(drive_id)
            par_enseigne[enseigne].append(
                magasin_retrait(drive_id, point, point.coordonnees or (m["lat"], m["lon"]))
            )
            continue
        par_enseigne[enseigne].append(
            Magasin(
                id=Magasin.fabriquer_id(enseigne, "osm" + m["id"]),
                enseigne=enseigne,
                id_enseigne="osm" + m["id"],
                nom=m["nom"],
                adresse=", ".join(filter(None, [m["adresse"], m["code_postal"], m["ville"]])),
                code_postal=m["code_postal"],
                ville=m["ville"],
                position=Position(lat=m["lat"], lon=m["lon"]),
            )
        )
    for magasin in _magasins_initiaux():
        if magasin.id not in drives_associes:
            par_enseigne[magasin.enseigne].append(magasin)
    return par_enseigne


async def _magasins_enseigne(
    enseigne: Enseigne,
    source: SourcePrix,
    position: Position,
    rayon: float,
    maximum: int,
    reglages: Reglages,
) -> list[Magasin]:
    try:
        async with asyncio.timeout(reglages.timeout_enseigne_s):
            trouves = await source.trouver_magasins(position, rayon, maximum)
    except (SourceIndisponible, TimeoutError) as erreur:
        logger.info("Pas de magasins %s : %s", enseigne.nom, erreur or "délai dépassé")
        return []
    except Exception:
        logger.exception("Erreur inattendue en cherchant les magasins %s", enseigne.nom)
        return []
    return _garder_proches(trouves, position, rayon, maximum)


async def magasins_proches(
    lieu: str,
    reglages: Reglages,
    rayon_km: float | None = None,
    *,
    lieu_enregistre: tuple[str, Position] | None = None,
    seulement_drives: bool = False,
) -> MagasinsReponse:
    """Lève CodePostalInvalide ou CodePostalInconnu si le lieu ne convient pas.

    `seulement_drives` (mode « données réelles ») : seulement les points de retrait pris en charge par Edge."""
    ville, position = lieu_enregistre or await geocoder(lieu, reglages)
    rayon, maximum = _limites(rayon_km, reglages)
    sources = sources_actives(reglages)
    if seulement_drives:
        initiaux = (
            (m for ms in magasins_osm().values() for m in ms if m.id in DRIVES)
            if FICHIER_OSM.exists()
            else _magasins_initiaux()
        )
        drives: dict[Enseigne, dict[str, Magasin]] = {e: {} for e in sources}
        inscrits = await asyncio.to_thread(magasins_inscrits, reglages.db_path)
        for magasin in chain(initiaux, inscrits):
            if magasin.enseigne in drives:
                drives[magasin.enseigne][magasin.id] = magasin
        listes = [_garder_proches(ms.values(), position, rayon, maximum) for ms in drives.values()]
    elif reglages.magasins_osm and FICHIER_OSM.exists():
        tous = magasins_osm()
        listes = [_garder_proches(tous[e], position, rayon, maximum) for e in sources]
    else:
        listes = await asyncio.gather(
            *(
                _magasins_enseigne(e, s, position, rayon, maximum, reglages)
                for e, s in sources.items()
            )
        )
    return MagasinsReponse(
        code_postal=" ".join(lieu.split()),
        ville=ville,
        position=position,
        magasins=sorted(chain.from_iterable(listes), key=lambda m: m.distance_km),
        enseignes_sans_magasin=[e for e, liste in zip(sources, listes, strict=True) if not liste],
        rayon_km=rayon_km,
    )
