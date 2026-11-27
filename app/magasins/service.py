"""Magasins proches : interroge chaque source en parallèle, calcule les distances, garde les plus proches."""

import asyncio
import logging
import math
from itertools import chain

from app.config import Reglages
from app.contrats import Enseigne, Magasin, MagasinsReponse, Position
from app.magasins.geocodage import geocoder
from app.sources.base import SourceIndisponible, SourcePrix
from app.sources.registre import sources_actives

logger = logging.getLogger(__name__)


def distance_km(a: Position, b: Position) -> float:
    """Distance à vol d'oiseau (formule de haversine)."""
    rayon_terre = 6371.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = phi2 - phi1
    dlambda = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * rayon_terre * math.asin(math.sqrt(h))


async def _magasins_enseigne(
    enseigne: Enseigne, source: SourcePrix, position: Position, reglages: Reglages
) -> list[Magasin]:
    try:
        async with asyncio.timeout(reglages.timeout_enseigne_s):
            trouves = await source.trouver_magasins(
                position, reglages.rayon_km, reglages.max_magasins_par_enseigne
            )
    except (SourceIndisponible, TimeoutError) as erreur:
        logger.info("Pas de magasins %s : %s", enseigne.nom, erreur or "délai dépassé")
        return []
    except Exception:
        logger.exception("Erreur inattendue en cherchant les magasins %s", enseigne.nom)
        return []

    proches = []
    for magasin in trouves:
        distance = distance_km(position, magasin.position)
        if distance <= reglages.rayon_km:
            proches.append(magasin.model_copy(update={"distance_km": round(distance, 1)}))
    proches.sort(key=lambda m: m.distance_km)
    return proches[: reglages.max_magasins_par_enseigne]


async def magasins_proches(code_postal: str, reglages: Reglages) -> MagasinsReponse:
    """Lève CodePostalInvalide ou CodePostalInconnu si le code postal ne convient pas."""
    ville, position = await geocoder(code_postal, reglages)
    sources = sources_actives(reglages)
    listes = await asyncio.gather(
        *(_magasins_enseigne(e, s, position, reglages) for e, s in sources.items())
    )
    return MagasinsReponse(
        code_postal=code_postal.strip(),
        ville=ville,
        position=position,
        magasins=sorted(chain.from_iterable(listes), key=lambda m: m.distance_km),
        enseignes_sans_magasin=[e for e, liste in zip(sources, listes, strict=True) if not liste],
    )
