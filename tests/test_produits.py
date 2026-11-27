"""Recherche d'articles (Open Food Facts), sur des réponses enregistrées le 27/11/2026 (tests/donnees/off/)."""

import json
from pathlib import Path

import httpx
import pytest

from app import db
from app.produits import service
from app.produits.service import (
    lire_quantite,
    mots_recherche,
    produit_par_ean,
    rechercher,
    separer_quantite,
)

pytestmark = pytest.mark.anyio
DONNEES = Path(__file__).parent / "donnees" / "off"
FICHIERS = {
    "nutella": "recherche_nutella.json",
    "lait demi-écrémé": "recherche_lait_demi-ecreme.json",
    "oeufs": "recherche_oeufs.json",
    "(nutella) AND quantity:(400*)": "recherche_nutella_quantite_400.json",
    "spag*": "recherche_spag_prefixe.json",
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
    assert (
        len(faux.requetes) == 2
    )  # « nutella* » et « nutella » ; la deuxième fois, tout vient du cache
    assert produit_par_ean(reglages_off, produits[0].ean) == produits[0]


async def test_panne_catalogue_fictif(reglages_off):
    faux = FauxOFF(statut=503)
    produits = await _chercher("nutella", reglages_off, faux)
    assert len(faux.requetes) == 2  # les deux recherches échouent
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


# --- Quantité dans la recherche (« nutella 400 g ») ---


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("400 g e", (400, "g")),
        ("1000g", (1000, "g")),
        ("1 kg", (1000, "g")),
        ("0.25 kg", (250, "g")),
        ("825 gr", (825, "g")),
        ("1,5 L", (1500, "ml")),
        ("1.5 Lts", (1500, "ml")),
        ("50 cl", (500, "ml")),
        ("6 x 1 L", (6000, "ml")),
        ("150 cl (6*25 cl)", (1500, "ml")),
        ("6", None),
        ("10 pcs", None),
        (None, None),
    ],
)
def test_lire_quantite(texte, attendu):
    assert lire_quantite(texte) == attendu


def test_separer_quantite():
    assert separer_quantite("nutella 400 g") == ("nutella", (400, "g"))
    assert separer_quantite("Lait demi-écrémé 1L") == ("Lait demi-écrémé", (1000, "ml"))
    assert separer_quantite("nutella") == ("nutella", None)


async def test_nutella_400_g_en_tete(reglages_off):
    faux = FauxOFF()
    produits = await _chercher("nutella 400 g", reglages_off, faux)
    assert produits, "la quantité ne doit pas vider la recherche"
    assert lire_quantite(produits[0].quantite) == (400, "g")
    assert produits[0].ean == "3017620422003"  # Nutella 400 g vendu en France
    # Recherche ciblée (7 résultats), puis début de mot (rien ici), puis recherche classique.
    assert [r.url.params["q"] for r in faux.requetes] == [
        "(nutella) AND quantity:(400*)",
        "nutella*",
        "nutella",
    ]
    assert len(produits) == 8


async def test_quantite_ecrite_autrement(reglages_off):
    # « 1 kg » trouve aussi les produits marqués « 1000g ».
    produits = await _chercher("nutella 1 kg", reglages_off, FauxOFF())
    assert lire_quantite(produits[0].quantite) == (1000, "g")


async def test_sans_quantite_pas_de_recherche_ciblee(reglages_off):
    faux = FauxOFF()
    await _chercher("nutella", reglages_off, faux)
    # Début de mot (rien dans les réponses enregistrées), puis recherche classique.
    assert [r.url.params["q"] for r in faux.requetes] == ["nutella*", "nutella"]


# --- Recherche pendant la frappe (« spag ») ---


def test_requete_prefixe():
    assert service.requete_prefixe("spag") == "spag*"
    assert service.requete_prefixe("pain de mi") == "pain AND de AND mi*"
    assert service.requete_prefixe("lait demi-écrémé") == "lait AND demi AND écrémé*"
    assert service.requete_prefixe("x") is None


def test_ligature_oe():
    assert service.normaliser("6 Gros Œufs") == "6 gros oeufs"


async def test_debut_de_mot_trouve_les_spaghetti(reglages_off):
    faux = FauxOFF()
    produits = await _chercher("spag", reglages_off, faux)
    assert faux.requetes[0].url.params["q"] == "spag*"
    assert faux.requetes[0].url.params["sort_by"] == "-unique_scans_n"
    assert len(faux.requetes) == 1  # assez de produits : pas de recherche classique en plus
    assert all(service.normaliser(p.libelle).startswith("spaghetti") for p in produits[:3])
    # Nom simple d'abord : pas de sauce ni de plat préparé en tête.
    assert "sauce" not in service.normaliser(produits[0].libelle)
