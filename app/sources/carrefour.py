"""Source Carrefour : collecte en direct (lot 3a). BOUCHON pour l'instant.

Repères (test du 27/11, détails dans l'annexe de docs/architecture.md) :
- sélection du Drive : GET https://www.carrefour.fr/set-store/<id> (ex. 136, Rennes Centre Alma),
  puis recherche : GET https://www.carrefour.fr/s?q=<recherche> avec les cookies de la sélection ;
- la page contient "routeData" : chaîne JSON d'un tableau aplati indexé (élément 0 = racine) ;
- prix : data[i].attributes.offers[ean]["<offerServiceId>"].attributes.price.price,
  promotions : .attributes.promotions[] (label, isLoyalty → TypePromo.FIDELITE…).
Au 27/11, curl reçoit 403 Cloudflare (`cf-mitigated: challenge`) : lever SourceIndisponible, ne
jamais contourner. Écrire le parseur et ses tests à partir d'une page enregistrée (tests/donnees/).
"""

from app.config import Reglages
from app.contrats import Enseigne, Magasin, Position, Prix, TypeSource
from app.sources.base import SourceIndisponible, SourcePrix


class SourceCarrefour(SourcePrix):
    enseigne = Enseigne.CARREFOUR
    type_source = TypeSource.COLLECTE
    nom = "Carrefour (site carrefour.fr)"

    def __init__(self, reglages: Reglages) -> None:
        self.reglages = reglages

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        raise SourceIndisponible("collecte Carrefour pas encore implémentée (lot 3a)")

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        raise SourceIndisponible("collecte Carrefour pas encore implémentée (lot 3a)")

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        raise SourceIndisponible("collecte Carrefour pas encore implémentée (lot 3a)")
