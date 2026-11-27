"""Lieu saisi → ville et position. Le lieu est un code postal, un nom de ville, ou une position GPS
« lat,lon » envoyée par le navigateur (bouton « Me localiser »).

D'abord une petite table intégrée (zone de démo, utilisable sans réseau), puis l'API Adresse de la
Géoplateforme (gratuite, sans clé) : /search pour un code postal ou une ville, /reverse pour une position.
"""

import re

import httpx

from app.config import Reglages
from app.contrats import Position


class CodePostalInvalide(ValueError):
    """Le texte saisi n'est ni un code postal, ni une ville, ni une position."""


class CodePostalInconnu(LookupError):
    """Lieu introuvable, ou service de géocodage injoignable."""


# Coordonnées relevées sur l'API Adresse le 27/11/2026.
CODES_POSTAUX_CONNUS: dict[str, tuple[str, Position]] = {
    "35170": ("Bruz", Position(lat=48.02516, lon=-1.748362)),
    "35000": ("Rennes", Position(lat=48.110899, lon=-1.68365)),
    "35200": ("Rennes", Position(lat=48.097194, lon=-1.653987)),
    "35700": ("Rennes", Position(lat=48.124217, lon=-1.657203)),
}

_deja_geocodes: dict[tuple[bool, str], tuple[str, Position]] = {}


async def _api_adresse(chemin: str, params: dict, reglages: Reglages) -> list[dict]:
    try:
        async with httpx.AsyncClient(
            timeout=reglages.timeout_requete_s,
            headers={"User-Agent": reglages.user_agent_services},
        ) as client:
            reponse = await client.get(f"{reglages.api_adresse_url}/{chemin}", params=params)
            reponse.raise_for_status()
            return reponse.json().get("features", [])
    except (httpx.HTTPError, ValueError):
        return []


async def adresse_proche(position: Position, reglages: Reglages) -> str | None:
    """Adresse postale la plus proche d'une position (« 9 Place du Docteur Joly 35170 Bruz »)."""
    for precision in ("housenumber", "street", None):
        params = {"lat": position.lat, "lon": position.lon, "limit": 1}
        if precision:
            params["type"] = precision
        trouves = await _api_adresse("reverse", params, reglages)
        if trouves:
            return trouves[0]["properties"].get("label")
    return None


async def geocoder(lieu: str, reglages: Reglages, *, adresse: bool = False) -> tuple[str, Position]:
    lieu = " ".join(lieu.split())
    if not lieu or len(lieu) > 160:
        raise CodePostalInvalide(lieu)
    if lieu in CODES_POSTAUX_CONNUS:
        return CODES_POSTAUX_CONNUS[lieu]
    cle = (adresse, lieu)
    if cle in _deja_geocodes:
        return _deja_geocodes[cle]

    coordonnees = re.fullmatch(r"(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)", lieu)
    if coordonnees:
        position = Position(lat=float(coordonnees[1]), lon=float(coordonnees[2]))
        if not (-90 <= position.lat <= 90 and -180 <= position.lon <= 180):
            raise CodePostalInvalide(lieu)
        if adresse:
            return "Votre position", position
        trouves = await _api_adresse(
            "reverse", {"lat": position.lat, "lon": position.lon, "limit": 1}, reglages
        )
        ville = trouves[0]["properties"].get("city", "") if trouves else ""
        return (ville or "votre position", position)

    if re.fullmatch(r"\d{5}", lieu):
        params = {"q": lieu, "postcode": lieu, "limit": 1}
    elif re.fullmatch(r"\d+", lieu):
        raise CodePostalInvalide(lieu)
    else:
        params = {"q": lieu, "limit": 1}
        # Une adresse complète (« 9 Place du Docteur Joly 35170 Bruz », venue de « Me localiser ») est
        # cherchée telle quelle ; un nom seul (« Rennes ») est cherché parmi les communes.
        if not adresse and not re.match(r"\d+\s*(bis|ter)?\s+\D", lieu, re.I):
            params["type"] = "municipality"
    trouves = await _api_adresse("search", params, reglages)
    if not trouves:
        raise CodePostalInconnu(lieu)

    lon, lat = trouves[0]["geometry"]["coordinates"]
    ville = trouves[0]["properties"].get("city", "")
    _deja_geocodes[cle] = (ville, Position(lat=lat, lon=lon))
    return _deja_geocodes[cle]
