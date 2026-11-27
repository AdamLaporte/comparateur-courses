"""Code postal → ville et position.

D'abord une petite table intégrée (zone de démo, utilisable sans réseau), puis l'API Adresse de la
Géoplateforme (gratuite, sans clé) : GET {api_adresse_url}/search?q=<cp>&postcode=<cp>&limit=1.
"""

import re

import httpx

from app.config import Reglages
from app.contrats import Position


class CodePostalInvalide(ValueError):
    """Le texte saisi n'est pas un code postal à 5 chiffres."""


class CodePostalInconnu(LookupError):
    """Code postal introuvable, ou service de géocodage injoignable."""


# Coordonnées relevées sur l'API Adresse le 27/11/2026.
CODES_POSTAUX_CONNUS: dict[str, tuple[str, Position]] = {
    "35170": ("Bruz", Position(lat=48.02516, lon=-1.748362)),
    "35000": ("Rennes", Position(lat=48.110899, lon=-1.68365)),
    "35200": ("Rennes", Position(lat=48.097194, lon=-1.653987)),
    "35700": ("Rennes", Position(lat=48.124217, lon=-1.657203)),
}

_deja_geocodes: dict[str, tuple[str, Position]] = {}


async def geocoder(code_postal: str, reglages: Reglages) -> tuple[str, Position]:
    code_postal = code_postal.strip()
    if not re.fullmatch(r"\d{5}", code_postal):
        raise CodePostalInvalide(code_postal)
    if code_postal in CODES_POSTAUX_CONNUS:
        return CODES_POSTAUX_CONNUS[code_postal]
    if code_postal in _deja_geocodes:
        return _deja_geocodes[code_postal]

    try:
        async with httpx.AsyncClient(
            timeout=reglages.timeout_requete_s,
            headers={"User-Agent": reglages.user_agent_services},
        ) as client:
            reponse = await client.get(
                f"{reglages.api_adresse_url}/search",
                params={"q": code_postal, "postcode": code_postal, "limit": 1},
            )
            reponse.raise_for_status()
            resultats = reponse.json().get("features", [])
    except (httpx.HTTPError, ValueError) as erreur:
        raise CodePostalInconnu(code_postal) from erreur
    if not resultats:
        raise CodePostalInconnu(code_postal)

    lon, lat = resultats[0]["geometry"]["coordinates"]
    ville = resultats[0]["properties"].get("city", "")
    _deja_geocodes[code_postal] = (ville, Position(lat=lat, lon=lon))
    return _deja_geocodes[code_postal]
