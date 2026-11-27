"""Source Courses U : collecte en direct (lot 3c). BOUCHON pour l'instant.

Au 27/11, coursesu.com répond 403 (Cloudflare) à une requête sans navigateur : lever
SourceIndisponible, ne jamais contourner. Chercher en priorité le JSON chargé par le site.
Écrire le parseur et ses tests à partir de réponses enregistrées (tests/donnees/).
"""

from app.config import Reglages
from app.contrats import Enseigne, Magasin, Position, Prix, TypeSource
from app.sources.base import SourceIndisponible, SourcePrix


class SourceCoursesU(SourcePrix):
    enseigne = Enseigne.COURSES_U
    type_source = TypeSource.COLLECTE
    nom = "Courses U (site coursesu.com)"

    def __init__(self, reglages: Reglages) -> None:
        self.reglages = reglages

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        raise SourceIndisponible("collecte Courses U pas encore implémentée (lot 3c)")

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        raise SourceIndisponible("collecte Courses U pas encore implémentée (lot 3c)")

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        raise SourceIndisponible("collecte Courses U pas encore implémentée (lot 3c)")
