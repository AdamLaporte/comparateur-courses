"""Orchestrateur de collecte : interroge les sources en parallèle et rend chaque prix dès qu'il arrive.

Pour « lignes × magasins » :
- toutes les enseignes en parallèle (asyncio) ;
- au plus CONCURRENCE_PAR_ENSEIGNE requêtes simultanées par enseigne (asyncio.Semaphore) ;
- au plus TIMEOUT_ENSEIGNE_S secondes par enseigne : ce qui n'est pas arrivé passe au repli ;
- toute erreur d'une source passe au repli (cache, Open Prices, « prix indisponible ») ;
- une enseigne lente ou en échec n'empêche jamais d'afficher les autres.
Ne dépend que de l'interface SourcePrix.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

from app.collecte import cache, repli
from app.config import Reglages
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Prix,
    ResultatLigne,
    StatutPrix,
    TypeSource,
)
from app.sources.base import SourceIndisponible, SourcePrix

logger = logging.getLogger(__name__)


def choisir_equivalent(offres: list[Prix]) -> Prix | None:
    """Mode « équivalent » : l'offre la moins chère, au prix unitaire si toutes l'ont, sinon au prix.

    Règle volontairement simple ; le lot 4 (règles d'équivalence, mode fin de mois) peut l'affiner.
    """
    if not offres:
        return None
    if all(o.prix_unitaire_centimes is not None for o in offres):
        return min(offres, key=lambda o: (o.prix_unitaire_centimes, o.prix_centimes))
    return min(offres, key=lambda o: o.prix_centimes)


async def resoudre(
    source: SourcePrix, ligne: LigneListe, magasin: Magasin, reglages: Reglages
) -> ResultatLigne:
    """Prix d'une ligne dans un magasin. Ne lève jamais d'exception."""
    cle = cache.cle_recherche(ligne)
    avec_cache = source.type_source != TypeSource.FICTIVE  # on ne met jamais du fictif en cache
    if avec_cache and (prix := cache.lire_frais(reglages, magasin.enseigne, magasin.id, cle)):
        return ResultatLigne(
            ligne_id=ligne.id, magasin_id=magasin.id, statut=StatutPrix.TROUVE, prix=prix
        )

    try:
        if ligne.mode == ModeLigne.PRODUIT and ligne.ean:
            prix = await source.obtenir_prix(magasin, ligne.ean)
        else:
            prix = choisir_equivalent(await source.chercher_produits(magasin, ligne.recherche))
    except SourceIndisponible as erreur:
        return await repli.prix_de_secours(ligne, magasin, reglages, raison=str(erreur))
    except Exception as erreur:
        logger.exception("Erreur inattendue de la source %s", source.nom)
        return await repli.prix_de_secours(ligne, magasin, reglages, raison=repr(erreur))

    if prix is None:
        return ResultatLigne(
            ligne_id=ligne.id,
            magasin_id=magasin.id,
            statut=StatutPrix.INTROUVABLE,
            remarque="Absent de ce magasin",
        )
    if avec_cache:
        cache.ecrire(reglages, magasin.enseigne, magasin.id, cle, prix)
    return ResultatLigne(
        ligne_id=ligne.id, magasin_id=magasin.id, statut=StatutPrix.TROUVE, prix=prix
    )


async def collecter(
    lignes: list[LigneListe],
    magasins: list[Magasin],
    sources: dict[Enseigne, SourcePrix],
    reglages: Reglages,
) -> AsyncIterator[ResultatLigne]:
    """Rend un ResultatLigne par couple (ligne, magasin), dans l'ordre d'arrivée."""
    if not lignes or not magasins:
        return

    file: asyncio.Queue[ResultatLigne | None] = asyncio.Queue()
    magasins_par_enseigne: dict[Enseigne, list[Magasin]] = defaultdict(list)
    for magasin in magasins:
        magasins_par_enseigne[magasin.enseigne].append(magasin)

    async def traiter_enseigne(enseigne: Enseigne, ses_magasins: list[Magasin]) -> None:
        restantes = {(lg.id, m.id): (lg, m) for m in ses_magasins for lg in lignes}
        try:
            source = sources.get(enseigne)
            if source is not None:
                semaphore = asyncio.Semaphore(reglages.concurrence_par_enseigne)

                async def traiter(ligne: LigneListe, magasin: Magasin) -> None:
                    async with semaphore:
                        resultat = await resoudre(source, ligne, magasin, reglages)
                    if restantes.pop((ligne.id, magasin.id), None) is not None:
                        await file.put(resultat)

                try:
                    async with asyncio.timeout(reglages.timeout_enseigne_s):
                        await asyncio.gather(
                            *(traiter(lg, m) for lg, m in list(restantes.values())),
                            return_exceptions=True,
                        )
                except TimeoutError:
                    logger.warning(
                        "%s : délai de %s s dépassé, %d prix passent au repli",
                        enseigne.nom,
                        reglages.timeout_enseigne_s,
                        len(restantes),
                    )
            # Tout ce qui n'a pas abouti (délai, source absente) passe au repli.
            for cle_tache, (ligne, magasin) in list(restantes.items()):
                del restantes[cle_tache]
                raison = "délai dépassé" if source else "aucune source configurée"
                await file.put(await repli.prix_de_secours(ligne, magasin, reglages, raison))
        finally:
            await file.put(None)  # cette enseigne a fini

    taches = [
        asyncio.create_task(traiter_enseigne(enseigne, ses_magasins))
        for enseigne, ses_magasins in magasins_par_enseigne.items()
    ]
    try:
        enseignes_en_cours = len(taches)
        while enseignes_en_cours:
            element = await file.get()
            if element is None:
                enseignes_en_cours -= 1
            else:
                yield element
    finally:
        for tache in taches:
            tache.cancel()
        await asyncio.gather(*taches, return_exceptions=True)
