"""Mode des données : « démo » (tous les magasins, prix fictifs, aucune requête Edge) ou « réel »
(drives répertoriés seulement, relevés Edge, rien de fictif)."""

import re

import pytest

from app import db
from app.drives.modeles import DRIVES


@pytest.fixture
def site(client, reglages):
    reglages.magasins_osm = True  # vrais magasins, dont les drives répertoriés
    reglages.drives_jeton = "j" * 32  # collecte Edge configurée : seul le mode doit l'empêcher
    reglages.drives_attente_s = 0  # l'extension ne répond pas : le flux se termine tout de suite
    return client


def _magasins_affiches(client) -> set[str]:
    page = client.get("/panier/resultats").text
    return set(re.findall(r'data-magasin="([^"]+)"', page))


def _preparer(client, rayon="10"):
    client.get("/magasins", params={"code_postal": "35170", "rayon_km": rayon})
    client.post("/panier/lignes", data={"mode": "equivalent", "recherche": "lait"})


def _taches(reglages) -> int:
    with db.connexion(reglages.db_path) as cnx:
        return cnx.execute("SELECT count(*) FROM drive_tache").fetchone()[0]


def test_demo_par_defaut_tous_les_magasins_prix_fictifs_sans_edge(site, reglages):
    assert "Passer aux données réelles" not in site.get("/").text  # plus dans le menu ni en bandeau
    page = site.get("/comptes").text  # replié en bas de la page Compte
    assert "Options de démonstration" in page and "Passer aux données réelles" in page

    _preparer(site)
    magasins = _magasins_affiches(site)
    assert any(m in DRIVES for m in magasins)  # les drives sont là…
    assert any(m not in DRIVES for m in magasins)  # … avec les autres magasins

    flux = site.get("/panier/prix/flux").text
    assert "Données fictives" in flux  # drives compris : prix fictifs
    assert "Recherche sur le drive" not in flux
    assert _taches(reglages) == 0  # aucune requête aux extensions Edge


def test_reel_seulement_les_drives_releves_edge_rien_de_fictif(site, reglages):
    reponse = site.post(
        "/mode-donnees", data={"mode": "reel", "suivant": "/panier"}, follow_redirects=False
    )
    assert reponse.status_code == 303 and reponse.headers["location"] == "/panier"
    assert "Passer en démo" in site.get("/comptes").text

    _preparer(site)
    magasins = _magasins_affiches(site)
    assert magasins and magasins <= set(DRIVES)  # seulement des drives répertoriés

    flux = site.get("/panier/prix/flux").text
    assert "Données fictives" not in flux
    assert _taches(reglages) > 0  # une recherche a été demandée aux extensions


def test_page_des_magasins_en_mode_reel(site):
    site.post("/mode-donnees", data={"mode": "reel"})
    page = site.get("/magasins", params={"code_postal": "35170"}).text
    assert "Super U Bruz" in page
    assert "osm" not in " ".join(re.findall(r'data-magasin="([^"]+)"', page))


def test_retour_en_demo(site, reglages):
    site.post("/mode-donnees", data={"mode": "reel"})
    site.post("/mode-donnees", data={"mode": "demo"})
    _preparer(site)
    site.get("/panier/prix/flux")
    assert _taches(reglages) == 0


def test_mode_par_defaut_reglable_et_choix_invalide_ignore(site, reglages):
    reglages.mode_donnees_defaut = "reel"
    assert "Passer en démo" in site.get("/comptes").text
    site.post("/mode-donnees", data={"mode": "n-importe-quoi"})
    assert "Passer en démo" in site.get("/comptes").text


def test_pas_de_redirection_hors_du_site(site):
    reponse = site.post(
        "/mode-donnees",
        data={"mode": "reel", "suivant": "//pirate.example.org/"},
        follow_redirects=False,
    )
    assert reponse.headers["location"] == "/"
