"""Recherche d'articles (Open Food Facts), sur des réponses enregistrées le 27/11/2026 (tests/donnees/off/)."""

import json
from pathlib import Path

import httpx
import pytest

from app import db
from app.produits import service
from app.produits.service import mots_recherche, produit_par_ean, rechercher

pytestmark = pytest.mark.anyio
DONNEES = Path(__file__).parent / "donnees" / "off"
FICHIERS = {
    "nutella": "recherche_nutella.json",
    "lait demi-écrémé": "recherche_lait_demi-ecreme.json",
    "oeufs": "recherche_oeufs.json",
}


class FauxOFF:
    def __init__(self, statut: int = 200):
        self.requetes: list[httpx.Request] = []
        self.statut = statut

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if self.statut != 200:
            return httpx.Response(self.statut)
        fichier = FICHIERS.get(requete.url.params["q"])
        if fichier is None:
            return httpx.Response(200, json={"hits": [], "count": 0})
        return httpx.Response(200, json=json.loads((DONNEES / fichier).read_text("utf-8")))


@pytest.fixture
def reglages_off(reglages, monkeypatch):
    db.initialiser(reglages.db_path)
    reglages.source_produits = "open_food_facts"
    monkeypatch.setattr(service, "INTERVALLE_MIN_S", 0)
    return reglages


async def _chercher(texte, reglages, faux):
    return await rechercher(texte, reglages, transport=httpx.MockTransport(faux))


def test_mots_recherche():
    assert mots_recherche("Pâte à tartiner") == ["pate", "tartiner"]
    assert mots_recherche("oeufs") == ["oeuf"]
    assert mots_recherche("lait demi-écrémé") == ["lait", "demi", "ecreme"]


async def test_nutella_produits_francais_en_tete(reglages_off):
    produits = await _chercher("nutella", reglages_off, FauxOFF())
    assert 0 < len(produits) <= 8
    assert produits[0].ean.startswith("3017620")  # Nutella vendu en France (Ferrero France)
    assert all("nutella" in p.libelle.lower() for p in produits[:3])
    assert produits[0].marque and not produits[0].marque.startswith("xx:")


async def test_tous_les_mots_avant_les_autres(reglages_off):
    produits = await _chercher("lait demi-écrémé", reglages_off, FauxOFF())
    premiers = [service.normaliser(p.libelle) for p in produits[:5]]
    assert all("lait" in t and "demi" in t and "ecreme" in t for t in premiers)


async def test_pluriel(reglages_off):
    produits = await _chercher("oeufs", reglages_off, FauxOFF())
    assert produits and "oeuf" in service.normaliser(produits[0].libelle)


async def test_cache_et_table_produit(reglages_off):
    faux = FauxOFF()
    produits = await _chercher("nutella", reglages_off, faux)
    await _chercher("  Nutella ", reglages_off, faux)
    assert len(faux.requetes) == 1  # deuxième recherche servie par le cache
    assert produit_par_ean(reglages_off, produits[0].ean) == produits[0]


async def test_panne_catalogue_fictif(reglages_off):
    faux = FauxOFF(statut=503)
    produits = await _chercher("nutella", reglages_off, faux)
    assert len(faux.requetes) == 1
    assert produits and produits[0].ean == "3017620422003"  # Nutella du catalogue fictif


async def test_panne_apres_une_reponse_enregistree(reglages_off, monkeypatch):
    await _chercher("nutella", reglages_off, FauxOFF())
    monkeypatch.setattr(service, "DUREE_REPONSE_MIN", -1)  # tout est périmé
    produits = await _chercher("nutella", reglages_off, FauxOFF(statut=503))
    assert produits[0].ean.startswith("3017620")  # ancienne réponse, pas le catalogue fictif


async def test_mode_fictif_sans_reseau(reglages_off):
    reglages_off.source_produits = "fictive"
    faux = FauxOFF()
    assert await _chercher("nutella", reglages_off, faux)
    assert faux.requetes == []


async def test_recherche_trop_courte(reglages_off):
    faux = FauxOFF()
    assert await _chercher(" n ", reglages_off, faux) == []
    assert faux.requetes == []
