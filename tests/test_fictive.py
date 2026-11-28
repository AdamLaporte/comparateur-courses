"""Données fictives (mode démo) : chaque article a un prix dans chaque magasin."""

import pytest

from app.collecte.orchestrateur import collecter
from app.contrats import Enseigne, LigneListe, ModeLigne, Position, StatutPrix
from app.sources.fictive import CATALOGUE, SourceFictive, rechercher_catalogue

pytestmark = pytest.mark.anyio
POSITION = Position(lat=48.02516, lon=-1.748362)
RECHERCHES = [
    "lait", "pâtes", "œufs", "riz", "café", "pain de mie", "beurre", "bananes", "avocat",
    "crème fraîche 20 cl", "carré frais", "farine", "sucre", "huile", "jambon", "pizza",
    "lessive", "dentifrice", "licorne arc-en-ciel",
]  # fmt: skip


async def _magasins(enseigne: Enseigne):
    return await SourceFictive(enseigne).trouver_magasins(POSITION, 10, 3)


@pytest.mark.parametrize("enseigne", list(Enseigne))
async def test_chaque_article_a_un_prix_dans_chaque_magasin(enseigne):
    source = SourceFictive(enseigne)
    eans = [a.ean for a in CATALOGUE] + ["3487400006721"]
    for magasin in await _magasins(enseigne):
        for ean in eans:  # y compris les marques distributeur des autres enseignes
            prix = await source.obtenir_prix(magasin, ean)
            assert prix is not None and prix.prix_centimes > 0 and prix.est_fictif, ean
        for recherche in RECHERCHES:
            offres = await source.chercher_produits(magasin, recherche)
            assert offres and all(o.est_fictif for o in offres), recherche


@pytest.mark.parametrize(
    ("recherche", "attendu"),
    [
        ("avocat", "Avocat"),
        ("crème fraîche 20 cl", "Crème fraîche"),
        ("carré frais", "Carré frais"),
        ("nutella 400 g", "Pâte à tartiner"),
        ("œufs x12", "Œufs"),
        ("licorne arc-en-ciel", "Licorne arc-en-ciel"),
    ],
)
async def test_le_prix_porte_sur_le_bon_article(recherche, attendu):
    magasin = (await _magasins(Enseigne.LECLERC))[0]
    offres = await SourceFictive(Enseigne.LECLERC).chercher_produits(magasin, recherche)
    assert offres and all(o.produit.libelle.startswith(attendu) for o in offres)


def test_un_mot_ne_correspond_pas_au_milieu_d_un_autre():
    assert rechercher_catalogue("ate") == []  # « pâte », « tomate »


async def test_aucun_manquant_dans_la_comparaison_de_demo(reglages):
    lignes = [
        LigneListe(id=1, mode=ModeLigne.PRODUIT, ean="3487400006721", recherche="riz",
                   libelle="Riz Basmati 220 g"),
        LigneListe(id=2, mode=ModeLigne.INEXISTANT, recherche="pasta box", libelle="pasta box"),
        *(
            LigneListe(id=i, mode=ModeLigne.EQUIVALENT, recherche=r, libelle=r)
            for i, r in enumerate(RECHERCHES, start=3)
        ),
    ]  # fmt: skip
    # Avec le délai simulé, une longue liste ne doit pas dépasser le temps laissé à l'enseigne.
    reglages.timeout_enseigne_s = 1.0
    magasins = (await _magasins(Enseigne.CARREFOUR))[:2]
    sources = {Enseigne.CARREFOUR: SourceFictive(Enseigne.CARREFOUR, 0.2)}
    resultats = [r async for r in collecter(lignes, magasins, sources, reglages)]
    assert len(resultats) == len(lignes) * 2
    assert all(r.statut == StatutPrix.TROUVE for r in resultats)
    precis = [r.prix.produit.libelle for r in resultats if r.ligne_id == 1]
    assert precis == ["Riz Basmati 220 g"] * 2  # pas « Article 3487400006721 »
