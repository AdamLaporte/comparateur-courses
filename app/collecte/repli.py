"""Repli quand la source d'une enseigne échoue (403, défi anti-robots, délai, clé absente…).

Ordre : 1) dernier prix en cache, même périmé, avec sa date ; 2) Open Prices ; 3) « prix indisponible ».
L'utilisateur ne voit jamais l'erreur brute : la raison technique va seulement dans les journaux.
Le niveau 2 n'envoie aucune requête si OPEN_PRICES_ACTIF=false (il utilise alors seulement les
réponses Open Prices déjà enregistrées, par exemple par le préchauffage).
"""

import asyncio
import logging

from app.collecte import cache
from app.collecte.equivalence import choisir_equivalent
from app.config import Reglages
from app.contrats import LigneListe, Magasin, ModeLigne, ResultatLigne, StatutPrix
from app.sources.base import SourceIndisponible
from app.sources.open_prices import SourceOpenPrices

logger = logging.getLogger(__name__)


async def prix_de_secours(
    ligne: LigneListe, magasin: Magasin, reglages: Reglages, raison: str
) -> ResultatLigne:
    logger.info("Repli pour %s / ligne %s : %s", magasin.id, ligne.id, raison)

    # 1. Dernier prix connu, même périmé.
    prix = cache.lire_dernier(reglages, magasin.enseigne, magasin.id, cache.cle_recherche(ligne))
    if prix is not None:
        return ResultatLigne(
            ligne_id=ligne.id,
            magasin_id=magasin.id,
            statut=StatutPrix.TROUVE,
            prix=prix,
            remarque="Dernier prix connu",
        )

    # 2. Open Prices (relevés de la communauté).
    open_prices = SourceOpenPrices(reglages)
    try:
        async with asyncio.timeout(reglages.timeout_requete_s):
            if ligne.mode == ModeLigne.PRODUIT and ligne.ean:
                prix = await open_prices.obtenir_prix(magasin, ligne.ean)
            else:
                offres = await open_prices.chercher_produits(magasin, ligne.recherche)
                prix = choisir_equivalent(offres)
    except (SourceIndisponible, TimeoutError):
        prix = None
    except Exception:
        logger.exception("Open Prices a échoué pour %s", magasin.id)
        prix = None
    if prix is not None:
        return ResultatLigne(
            ligne_id=ligne.id,
            magasin_id=magasin.id,
            statut=StatutPrix.TROUVE,
            prix=prix,
            remarque="Relevé Open Prices",
        )

    # 3. Rien d'exploitable.
    return ResultatLigne(
        ligne_id=ligne.id,
        magasin_id=magasin.id,
        statut=StatutPrix.INDISPONIBLE,
        remarque="Prix indisponible",
    )
