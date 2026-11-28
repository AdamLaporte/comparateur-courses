"""Orchestrateur de collecte : interroge les sources en parallèle et rend chaque prix dès qu'il arrive.

Pour « lignes × magasins » :
- toutes les enseignes en parallèle (asyncio) ;
- au plus CONCURRENCE_PAR_ENSEIGNE requêtes simultanées par enseigne (asyncio.Semaphore) ;
- au plus TIMEOUT_ENSEIGNE_S secondes par enseigne : ce qui n'est pas arrivé passe au repli ;
- toute erreur d'une source passe au repli (cache, Open Prices, « prix indisponible ») ;
- une enseigne lente ou en échec n'empêche jamais d'afficher les autres.
Les points de retrait Edge suivent leur propre file de collecte.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

from app.collecte import cache, repli
from app.collecte.equivalence import choisir_equivalent
from app.config import Reglages
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    ResultatLigne,
    StatutPrix,
    TypeSource,
)
from app.drives.comparaison import relever_ligne
from app.drives.modeles import DriveId, identifiant_drive_valide
from app.sources.base import SourceIndisponible, SourcePrix

logger = logging.getLogger(__name__)


async def resoudre(
    source: SourcePrix, ligne: LigneListe, magasin: Magasin, reglages: Reglages
) -> ResultatLigne:
    """Prix d'une ligne dans un magasin. Ne lève jamais d'exception."""
    if ligne.mode == ModeLigne.INEXISTANT:
        return ResultatLigne(
            ligne_id=ligne.id,
            magasin_id=magasin.id,
            statut=StatutPrix.INTROUVABLE,
            remarque="Article hors catalogue.",
        )
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
            prix = choisir_equivalent(
                await source.chercher_produits(magasin, ligne.recherche), ligne.recherche
            )
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
    *,
    suivre_edge: bool = False,
    drives_par_edge: bool = True,
) -> AsyncIterator[ResultatLigne]:
    """Rend les prix et les changements d'état Edge dans l'ordre d'arrivée.

    `drives_par_edge=False` (mode démo) : les drives sont traités comme les autres magasins, par la source
    de leur enseigne (fictive), et aucune requête n'est faite aux extensions Edge."""
    if not lignes or not magasins:
        return

    file: asyncio.Queue[ResultatLigne | None] = asyncio.Queue()
    magasins_par_enseigne: dict[Enseigne, list[Magasin]] = defaultdict(list)
    drives: list[DriveId] = []
    for magasin in magasins:
        if drives_par_edge and identifiant_drive_valide(magasin.id):
            drives.append(magasin.id)
        else:
            magasins_par_enseigne[magasin.enseigne].append(magasin)

    async def traiter_drive(drive: DriveId, ligne: LigneListe) -> None:
        try:
            async for resultat in relever_ligne(reglages, drive, ligne, suivre=suivre_edge):
                await file.put(resultat)
        except Exception:
            logger.exception("Relevé Edge impossible pour %s", drive)
            await file.put(
                ResultatLigne(
                    ligne_id=ligne.id,
                    magasin_id=drive,
                    statut=StatutPrix.INDISPONIBLE,
                    remarque="Relevé Edge indisponible.",
                )
            )
        finally:
            await file.put(None)

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
            # Tout ce qui n'a pas abouti (délai, source absente) passe au repli, en parallèle.
            raison = "délai dépassé" if source else "aucune source configurée"
            en_retard = list(restantes.values())
            restantes.clear()

            async def secourir(ligne: LigneListe, magasin: Magasin) -> None:
                await file.put(await repli.prix_de_secours(ligne, magasin, reglages, raison))

            await asyncio.gather(*(secourir(lg, m) for lg, m in en_retard))
        finally:
            await file.put(None)  # cette enseigne a fini

    taches = [
        asyncio.create_task(traiter_enseigne(enseigne, ses_magasins))
        for enseigne, ses_magasins in magasins_par_enseigne.items()
    ]
    taches.extend(
        asyncio.create_task(traiter_drive(drive, ligne)) for drive in drives for ligne in lignes
    )
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
