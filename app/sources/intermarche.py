"""Source Intermarché : API officielle (lot 2). BOUCHON pour l'instant.

Règle (docs/decisions.md) : sans INTERMARCHE_API_KEY, AUCUNE requête n'est envoyée.
`chercher_produits` et `obtenir_prix` lèvent alors `SourceNonConfiguree`, et l'orchestrateur passe
directement au repli (cache, Open Prices, « prix indisponible »).

À faire dans le lot 2 (voir docs/taches.md et l'annexe de docs/architecture.md) :
- lire les réponses Stores v1 et Produits v1 à partir des exemples des specs OpenAPI (tests sans réseau) ;
- magasins sans clé : liste fixe pour la zone de démo (Rennes, Bruz) ou magasins Intermarché d'Open Prices ;
- avec la clé : GET {intermarche_url_stores}/stores (en-tête X-Api-Key),
  POST {intermarche_url_produits}/pdvs/{pdvId}/produits/search (en-tête apikey), puis filtre sur l'EAN.
"""

from app.config import Reglages
from app.contrats import Enseigne, Magasin, Position, Prix, TypeSource
from app.sources.base import SourceIndisponible, SourceNonConfiguree, SourcePrix


class SourceIntermarche(SourcePrix):
    enseigne = Enseigne.INTERMARCHE
    type_source = TypeSource.API
    nom = "Intermarché (API officielle)"

    def __init__(self, reglages: Reglages) -> None:
        self.reglages = reglages
        self.cle = reglages.intermarche_api_key.strip()

    def _verifier_cle(self) -> None:
        if not self.cle:
            raise SourceNonConfiguree("INTERMARCHE_API_KEY vide : aucune requête envoyée à l'API")

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        if not self.cle:
            # Lot 2 : renvoyer ici la liste fixe (Rennes, Bruz) ou les magasins d'Open Prices.
            return []
        raise SourceIndisponible("API Stores pas encore branchée (lot 2)")

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        self._verifier_cle()
        raise SourceIndisponible("API Produits pas encore branchée (lot 2)")

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        self._verifier_cle()
        raise SourceIndisponible("API Produits pas encore branchée (lot 2)")
