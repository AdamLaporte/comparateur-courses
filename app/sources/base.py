"""Interface commune à toutes les sources de prix (fichier partagé : modification concertée).

Le reste de l'application ne dépend que de cette interface. Une source :
- implémente `trouver_magasins`, `chercher_produits` et `obtenir_prix` ;
- lève `SourceIndisponible` en cas d'échec (403, défi anti-robots, délai, format inattendu) ou
  `SourceNonConfiguree` s'il lui manque un réglage (ex. clé d'API) ;
- n'affiche jamais rien elle-même : l'orchestrateur passe alors au repli.

Règle de collecte : ne jamais contourner une protection anti-robots (voir AGENTS.md, règle 6).
"""

from abc import ABC, abstractmethod

import httpx

from app.contrats import Enseigne, Magasin, Position, Prix, TypeSource


class SourceIndisponible(Exception):
    """La source n'a pas pu répondre (échec réseau, 403, défi anti-robots, délai, format inattendu)."""


class SourceNonConfiguree(SourceIndisponible):
    """Il manque un réglage à la source (ex. INTERMARCHE_API_KEY vide) : aucune requête n'est envoyée."""


# En-têtes d'un navigateur ordinaire, pour les sources de collecte. Requêtes modérées seulement.
ENTETES_NAVIGATEUR = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
}


def nouveau_client(
    timeout_s: float, entetes: dict[str, str] | None = None, **options
) -> httpx.AsyncClient:
    """Client HTTP asynchrone commun (délai, redirections, en-têtes de navigateur par défaut)."""
    return httpx.AsyncClient(
        timeout=timeout_s,
        follow_redirects=True,
        headers=entetes if entetes is not None else ENTETES_NAVIGATEUR,
        **options,
    )


class SourcePrix(ABC):
    """Une source de prix. `enseigne` vaut None pour une source multi-enseignes (Open Prices)."""

    enseigne: Enseigne | None
    type_source: TypeSource
    nom: str  # libellé affiché avec chaque prix, ex. "Intermarché (API officielle)"

    @abstractmethod
    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        """Magasins de l'enseigne autour de la position (le tri par distance est fait ensuite)."""

    @abstractmethod
    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        """Produits du magasin qui correspondent à la recherche, avec leur prix et leurs promotions."""

    @abstractmethod
    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        """Prix et promotions d'un produit précis. None si le magasin ne l'a pas."""
