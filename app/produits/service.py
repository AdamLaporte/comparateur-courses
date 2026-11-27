"""Recherche d'articles.

Squelette : cherche dans le catalogue de la source fictive.
Lot 4 : interroger Open Food Facts (recherche texte → EAN, libellé, marque, quantité), en gardant le
catalogue fictif comme secours, et enregistrer les produits dans la table `produit` si besoin.
"""

from app.config import Reglages
from app.contrats import Produit
from app.sources.fictive import rechercher_catalogue


async def rechercher(texte: str, reglages: Reglages, limite: int = 8) -> list[Produit]:
    if len(texte.strip()) < 2:
        return []
    return [article.produit() for article in rechercher_catalogue(texte)[:limite]]
