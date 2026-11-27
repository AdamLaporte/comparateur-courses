"""Source Open Prices, sur des réponses enregistrées le 27/11/2026 (tests/donnees/open_prices/)."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app import db
from app.collecte import repli
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Position,
    StatutPrix,
    TypePromo,
    TypeSource,
)
from app.sources import open_prices
from app.sources.base import SourceIndisponible, SourceNonConfiguree
from app.sources.open_prices import SourceOpenPrices, enseigne_du_lieu, prix_depuis_releve

pytestmark = pytest.mark.anyio
DONNEES = Path(__file__).parent / "donnees" / "open_prices"

# Magasin réel de la zone de démo, à l'adresse du lieu Open Prices « E.Leclerc Cleunay ».
LECLERC_CLEUNAY = Magasin(
    id="leclerc-cleunay",
    enseigne=Enseigne.LECLERC,
    id_enseigne="cleunay",
    nom="E.Leclerc Rennes Cleunay",
    ville="Rennes",
    position=Position(lat=48.1049, lon=-1.7146),
)
LECLERC_BRUZ = LECLERC_CLEUNAY.model_copy(
    update={"id": "leclerc-bruz", "ville": "", "position": Position(lat=48.025, lon=-1.748)}
)


class FauxOpenPrices:
    """Sert les réponses enregistrées et compte les requêtes."""

    def __init__(self, panne: bool = False):
        self.requetes: list[httpx.Request] = []
        self.panne = panne

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if self.panne:
            return httpx.Response(503)
        params = requete.url.params
        if requete.url.path.endswith("/locations"):
            fichier = "lieux_rennes.json"
        elif params.get("location_id") == "6278":
            fichier = "prix_leclerc_cleunay.json"
        elif "lat" in params:
            fichier = "prix_autour_cleunay.json"
        else:
            return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "pages": 0})
        return httpx.Response(200, json=json.loads((DONNEES / fichier).read_text("utf-8")))


@pytest.fixture
def reglages_op(reglages, monkeypatch):
    db.initialiser(reglages.db_path)
    reglages.open_prices_actif = True
    monkeypatch.setattr(open_prices, "AGE_MAX_JOURS", 100 * 365)  # relevés de 2026 toujours valides
    return reglages


def _source(reglages, faux: FauxOpenPrices) -> SourceOpenPrices:
    return SourceOpenPrices(reglages, transport=httpx.MockTransport(faux))


def test_enseigne_du_lieu():
    assert (
        enseigne_du_lieu({"osm_brand": None, "osm_name": "E.Leclerc Cleunay"}) == Enseigne.LECLERC
    )
    assert enseigne_du_lieu({"osm_brand": "Intermarché Super"}) == Enseigne.INTERMARCHE
    assert enseigne_du_lieu({"osm_name": "U Express Rennes Liberté"}) == Enseigne.COURSES_U
    assert enseigne_du_lieu({"osm_brand": "Super U", "osm_name": "Super U"}) == Enseigne.COURSES_U
    assert enseigne_du_lieu({"osm_brand": "Carrefour Market"}) == Enseigne.CARREFOUR
    assert enseigne_du_lieu({"osm_brand": "NOZ", "osm_name": "NOZ"}) is None
    assert enseigne_du_lieu({"osm_name": "Boulangerie du Bourg"}) is None


async def test_lieu_le_plus_proche_de_meme_enseigne(reglages_op):
    source = _source(reglages_op, FauxOpenPrices())
    lieu = await source.lieu_du_magasin(LECLERC_CLEUNAY)
    assert lieu["id"] == 6278
    assert await source.lieu_du_magasin(LECLERC_BRUZ) is None


async def test_obtenir_prix_par_ean(reglages_op):
    prix = await _source(reglages_op, FauxOpenPrices()).obtenir_prix(
        LECLERC_CLEUNAY, "3383482309982"
    )
    assert prix is not None
    assert prix.prix_centimes == 699
    assert prix.produit.libelle == "Lessive peaux douces"
    assert prix.prix_unitaire_centimes == 437 and prix.unite == "L"  # 6,99 € / 1,6 L
    assert prix.source == TypeSource.OPEN_PRICES
    assert not prix.est_fictif
    assert prix.magasin_id == LECLERC_CLEUNAY.id
    assert prix.releve_le.date() == date(2026, 9, 26)
    assert "E.Leclerc Cleunay" in prix.source_detail and "26/09/2026" in prix.source_detail


async def test_produit_absent(reglages_op):
    source = _source(reglages_op, FauxOpenPrices())
    assert await source.obtenir_prix(LECLERC_CLEUNAY, "0000000000000") is None


async def test_magasin_sans_lieu(reglages_op):
    with pytest.raises(SourceIndisponible):
        await _source(reglages_op, FauxOpenPrices()).obtenir_prix(LECLERC_BRUZ, "3383482309982")


async def test_chercher_produits(reglages_op):
    offres = await _source(reglages_op, FauxOpenPrices()).chercher_produits(
        LECLERC_CLEUNAY, "Lotus Biscoff"
    )
    assert [o.prix_centimes for o in offres] == [156, 169, 182]
    assert (
        await _source(reglages_op, FauxOpenPrices()).chercher_produits(LECLERC_CLEUNAY, "x") == []
    )


async def test_reponses_en_cache_et_secours_hors_ligne(reglages_op):
    faux = FauxOpenPrices()
    await _source(reglages_op, faux).obtenir_prix(LECLERC_CLEUNAY, "3383482309982")
    nb = len(faux.requetes)
    assert nb > 0

    # Deuxième fois : tout vient du cache.
    await _source(reglages_op, faux).obtenir_prix(LECLERC_CLEUNAY, "3017760038331")
    assert len(faux.requetes) == nb

    # Open Prices désactivé : on se sert des réponses enregistrées, sans requête.
    reglages_op.open_prices_actif = False
    panne = FauxOpenPrices(panne=True)
    prix = await _source(reglages_op, panne).obtenir_prix(LECLERC_CLEUNAY, "3017760038331")
    assert prix.prix_centimes == 96
    assert panne.requetes == []


async def test_desactive_sans_cache_aucune_requete(reglages_op):
    reglages_op.open_prices_actif = False
    faux = FauxOpenPrices()
    with pytest.raises(SourceNonConfiguree):
        await _source(reglages_op, faux).obtenir_prix(LECLERC_CLEUNAY, "3383482309982")
    assert faux.requetes == []


async def test_service_en_panne(reglages_op):
    with pytest.raises(SourceIndisponible):
        await _source(reglages_op, FauxOpenPrices(panne=True)).obtenir_prix(
            LECLERC_CLEUNAY, "3383482309982"
        )


def test_prix_reduit():
    releve = {
        "type": "PRODUCT",
        "product_code": "3017620422003",
        "product": {
            "product_name": "Nutella",
            "product_quantity": 400,
            "product_quantity_unit": "g",
        },
        "price": 3.5,
        "price_is_discounted": True,
        "price_without_discount": 4.2,
        "currency": "EUR",
        "date": "2026-11-20",
        "created": "2026-11-21T08:00:00Z",
    }
    lieu = {"osm_name": "Carrefour Market", "osm_address_city": "Rennes"}
    prix = prix_depuis_releve(releve, LECLERC_CLEUNAY, lieu)
    assert prix.prix_centimes == 350 and prix.prix_barre_centimes == 420
    assert prix.promotions[0].type == TypePromo.IMMEDIATE
    assert prix.promotions[0].remise_centimes == 70
    assert prix.prix_unitaire_centimes == 875 and prix.unite == "kg"
    assert prix.releve_le.hour == 11  # envoyé le lendemain : heure inconnue, midi à Paris

    assert prix_depuis_releve({**releve, "type": "CATEGORY"}, LECLERC_CLEUNAY, lieu) is None
    assert prix_depuis_releve({**releve, "currency": "CHF"}, LECLERC_CLEUNAY, lieu) is None


async def test_trouver_magasins(reglages_op):
    magasins = await _source(reglages_op, FauxOpenPrices()).trouver_magasins(
        Position(lat=48.10512, lon=-1.714253), 2, 1
    )
    par_enseigne = {m.enseigne: m for m in magasins}
    assert par_enseigne[Enseigne.LECLERC].id == "leclerc-op-6278"
    assert par_enseigne[Enseigne.LECLERC].distance_km == 0.0
    assert Enseigne.CARREFOUR in par_enseigne
    assert len(magasins) == len(par_enseigne)  # au plus 1 par enseigne


async def test_repli_sur_open_prices(reglages_op, monkeypatch):
    faux = FauxOpenPrices()
    monkeypatch.setattr(repli, "SourceOpenPrices", lambda r: _source(r, faux))
    ligne = LigneListe(
        id=1, mode=ModeLigne.EQUIVALENT, recherche="biscoff", libelle="Biscoff", quantite=1
    )
    resultat = await repli.prix_de_secours(ligne, LECLERC_CLEUNAY, reglages_op, raison="403")
    assert resultat.statut == StatutPrix.TROUVE
    assert resultat.remarque == "Relevé Open Prices"
    assert resultat.prix.source == TypeSource.OPEN_PRICES
