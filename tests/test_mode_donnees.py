"""Mode des données : « démo » (tous les magasins, prix fictifs, aucune requête Edge) ou « réel »
(drives répertoriés seulement, relevés Edge, rien de fictif)."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import db
from app.drives.catalogue import inscrire
from app.drives.modeles import DRIVES
from app.main import creer_app


@pytest.fixture
def site(reglages):
    reglages.magasins_osm = True  # vrais magasins, dont les drives répertoriés
    reglages.drives_jeton = "j" * 32  # collecte Edge configurée : seul le mode doit l'empêcher
    reglages.drives_attente_s = 0  # l'extension ne répond pas : le flux se termine tout de suite
    with TestClient(creer_app(reglages), client=("127.0.0.1", 9999)) as client:
        yield client


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
    assert "Options de démonstration" in page and "Quitter la démo" in page
    assert "fictif" not in page.lower()

    _preparer(site)
    magasins = _magasins_affiches(site)
    assert any(m in DRIVES for m in magasins)  # les drives sont là…
    assert any(m not in DRIVES for m in magasins)  # … avec les autres magasins

    flux = site.get("/panier/prix/flux").text
    aujourdhui = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")
    assert f'<span class="source">{aujourdhui}</span>' in flux  # drives compris : prix fictifs…
    assert "fictif" not in flux.lower()  # … mais rien ne l'indique à l'écran
    assert "Recherche sur le drive" not in flux
    assert _taches(reglages) == 0  # aucune requête aux extensions Edge


def test_reel_seulement_les_drives_releves_edge_rien_de_fictif(site, reglages):
    reponse = site.post(
        "/mode-donnees", data={"mode": "reel", "suivant": "/panier"}, follow_redirects=False
    )
    assert reponse.status_code == 303 and reponse.headers["location"] == "/panier"
    page = site.get("/comptes").text
    assert "Passer en démo" in page and "prix fictifs" not in page

    _preparer(site, rayon="5")
    magasins = _magasins_affiches(site)
    assert magasins and magasins <= set(DRIVES)  # seulement des drives répertoriés
    assert {"carrefour-retrait-267", "leclerc-retrait-113511"} <= magasins

    site.get("/panier/prix/flux")  # lance la comparaison
    assert _taches(reglages) > 0  # une recherche a été demandée aux extensions
    for enseigne, reference in (("carrefour", "267"), ("leclerc", "113511")):
        tache = site.post(
            f"/api/drives/enseignes/{enseigne}/prendre",
            headers={"X-Drives-Jeton": reglages.drives_jeton},
        ).json()
        assert tache["drive_id"] == f"{enseigne}-retrait-{reference}"
        assert tache["point"]["reference"] == reference


def test_page_des_magasins_en_mode_reel(site):
    site.post("/mode-donnees", data={"mode": "reel"})
    page = site.get("/magasins", params={"code_postal": "35170"}).text
    assert "Super U Bruz" in page
    assert "osm" not in " ".join(re.findall(r'data-magasin="([^"]+)"', page))


def test_drives_geolocalises_sans_osm_et_sans_doublon(site, reglages, monkeypatch, tmp_path):
    monkeypatch.setattr("app.magasins.service.FICHIER_OSM", tmp_path / "osm-absent.json")
    drive = "leclerc-retrait-113511"
    point = DRIVES[drive].model_copy(update={"nom": "Drive de Ker Lann enregistré dans Edge"})
    inscrire(reglages.db_path, drive, point)

    site.post("/mode-donnees", data={"mode": "reel"})
    reponse = site.get("/magasins", params={"code_postal": "35170", "rayon_km": 5})
    assert reponse.status_code == 200
    assert "Carrefour Drive Chartres-de-Bretagne" in reponse.text
    assert point.nom in reponse.text
    assert "E.Leclerc Drive Bruz – Ker Lann" not in reponse.text
    points = site.post(
        "/api/drives/enseignes/leclerc/points-retrait",
        headers={"X-Drives-Jeton": reglages.drives_jeton},
    ).json()
    assert [p["nom"] for p in points if p["reference"] == "113511"] == [point.nom]


def test_retour_en_demo(site, reglages):
    site.post("/mode-donnees", data={"mode": "reel"})
    site.post("/mode-donnees", data={"mode": "demo"})
    _preparer(site)
    site.get("/panier/prix/flux")
    assert _taches(reglages) == 0


def test_mode_par_defaut_reglable_et_choix_invalide_ignore(site, reglages):
    reglages.mode_donnees_defaut = "reel"
    page = site.get("/comptes").text
    assert "Passer en démo" in page and "prix fictifs" not in page
    site.post("/mode-donnees", data={"mode": "n-importe-quoi"})
    page = site.get("/comptes").text
    assert "Passer en démo" in page and "prix fictifs" not in page


def test_pas_de_redirection_hors_du_site(site):
    reponse = site.post(
        "/mode-donnees",
        data={"mode": "reel", "suivant": "//pirate.example.org/"},
        follow_redirects=False,
    )
    assert reponse.headers["location"] == "/"
