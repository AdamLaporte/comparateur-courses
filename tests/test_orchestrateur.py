"""Orchestrateur de collecte : parallélisme, limites par enseigne, repli, règle Intermarché sans clé."""

import asyncio
import time

import httpx
import pytest

from app.collecte.orchestrateur import collecter
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Position,
    StatutPrix,
    TypeSource,
)
from app.sources.base import SourceIndisponible, SourceNonConfiguree, SourcePrix
from app.sources.fictive import SourceFictive
from app.sources.intermarche import SourceIntermarche

pytestmark = pytest.mark.anyio
POSITION = Position(lat=48.02516, lon=-1.748362)


def _lignes(n: int) -> list[LigneListe]:
    return [
        LigneListe(id=i, mode=ModeLigne.EQUIVALENT, recherche="lait", libelle="lait")
        for i in range(1, n + 1)
    ]


async def _magasins(enseigne: Enseigne, nombre: int = 2) -> list[Magasin]:
    return (await SourceFictive(enseigne).trouver_magasins(POSITION, 10, nombre))[:nombre]


async def _tout_collecter(lignes, magasins, sources, reglages):
    return [r async for r in collecter(lignes, magasins, sources, reglages)]


class SourceLente(SourceFictive):
    async def chercher_produits(self, magasin, recherche, limite=20):
        await asyncio.sleep(30)
        return []


class SourceEnPanne(SourceFictive):
    async def chercher_produits(self, magasin, recherche, limite=20):
        raise SourceIndisponible("403 défi anti-robots")


class SourceQuiCompte(SourceFictive):
    def __init__(self, enseigne):
        super().__init__(enseigne)
        self.en_cours = 0
        self.maximum = 0

    async def chercher_produits(self, magasin, recherche, limite=20):
        self.en_cours += 1
        self.maximum = max(self.maximum, self.en_cours)
        await asyncio.sleep(0.02)
        self.en_cours -= 1
        return await super().chercher_produits(magasin, recherche, limite)


async def test_une_enseigne_lente_ne_bloque_pas_les_autres(reglages):
    reglages.timeout_enseigne_s = 0.3
    lignes = _lignes(2)
    magasins = await _magasins(Enseigne.CARREFOUR) + await _magasins(Enseigne.LECLERC)
    sources: dict[Enseigne, SourcePrix] = {
        Enseigne.CARREFOUR: SourceLente(Enseigne.CARREFOUR),
        Enseigne.LECLERC: SourceFictive(Enseigne.LECLERC),
    }

    debut = time.monotonic()
    resultats = await _tout_collecter(lignes, magasins, sources, reglages)
    assert time.monotonic() - debut < 2

    assert len(resultats) == 2 * 4
    lents = [r for r in resultats if r.magasin_id.startswith("carrefour")]
    rapides = [r for r in resultats if r.magasin_id.startswith("leclerc")]
    assert all(r.statut == StatutPrix.INDISPONIBLE for r in lents)
    assert all(r.remarque == "Prix indisponible" for r in lents)
    assert all(r.statut != StatutPrix.INDISPONIBLE for r in rapides)


async def test_une_source_en_panne_passe_au_repli(reglages):
    lignes = _lignes(1)
    magasins = await _magasins(Enseigne.COURSES_U)
    sources = {Enseigne.COURSES_U: SourceEnPanne(Enseigne.COURSES_U)}
    resultats = await _tout_collecter(lignes, magasins, sources, reglages)
    assert len(resultats) == 2
    assert all(r.statut == StatutPrix.INDISPONIBLE for r in resultats)


async def test_concurrence_limitee_par_enseigne(reglages):
    reglages.concurrence_par_enseigne = 3
    source = SourceQuiCompte(Enseigne.CARREFOUR)
    lignes = _lignes(10)
    magasins = await _magasins(Enseigne.CARREFOUR)
    resultats = await _tout_collecter(lignes, magasins, {Enseigne.CARREFOUR: source}, reglages)
    assert len(resultats) == 20
    assert 1 < source.maximum <= 3


async def test_intermarche_sans_cle_aucune_requete(reglages, monkeypatch):
    async def requete_interdite(*args, **kwargs):
        raise AssertionError("aucune requête HTTP ne doit partir sans INTERMARCHE_API_KEY")

    monkeypatch.setattr(httpx.AsyncClient, "send", requete_interdite)
    reglages.intermarche_api_key = ""
    source = SourceIntermarche(reglages)
    magasin = (await _magasins(Enseigne.INTERMARCHE, 1))[0]

    with pytest.raises(SourceNonConfiguree):
        await source.obtenir_prix(magasin, "3017620422003")
    assert await source.trouver_magasins(POSITION, 10, 2) == []

    resultats = await _tout_collecter(
        _lignes(2), [magasin], {Enseigne.INTERMARCHE: source}, reglages
    )
    assert len(resultats) == 2
    assert all(r.statut == StatutPrix.INDISPONIBLE for r in resultats)


async def test_source_fictive_toujours_marquee(reglages):
    magasins = await _magasins(Enseigne.LECLERC)
    resultats = await _tout_collecter(
        _lignes(1), magasins, {Enseigne.LECLERC: SourceFictive(Enseigne.LECLERC)}, reglages
    )
    for resultat in resultats:
        if resultat.prix is not None:
            assert resultat.prix.est_fictif
            assert resultat.prix.source == TypeSource.FICTIVE
