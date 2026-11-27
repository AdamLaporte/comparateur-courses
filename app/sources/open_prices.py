"""Source Open Prices (API d'Open Food Facts) : source de secours (lot 4). BOUCHON pour l'instant.

Utilisée par app/collecte/repli.py quand la source d'une enseigne échoue.
Repères : {open_prices_url}/prices (filtres par product_code, location_osm_id…),
{open_prices_url}/locations (lieux OpenStreetMap avec osm_brand, osm_address_postcode…).
Peut aussi fournir des magasins Intermarché connus tant qu'il n'y a pas de clé (lot 2).
Chaque Prix renvoyé porte source=TypeSource.OPEN_PRICES et la date du relevé d'origine.
"""

from app.config import Reglages
from app.contrats import Magasin, Position, Prix, TypeSource
from app.sources.base import SourceIndisponible, SourcePrix


class SourceOpenPrices(SourcePrix):
    enseigne = None  # toutes enseignes
    type_source = TypeSource.OPEN_PRICES
    nom = "Open Prices (relevés de la communauté)"

    def __init__(self, reglages: Reglages) -> None:
        self.reglages = reglages

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        raise SourceIndisponible("Open Prices pas encore branché (lot 4)")

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        raise SourceIndisponible("Open Prices pas encore branché (lot 4)")

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        raise SourceIndisponible("Open Prices pas encore branché (lot 4)")
