import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import db
from app.drives import service
from app.main import creer_app
from app.site_partage import preparer

ORIGINE = "https://comparateur-test.equipe.ts.net"
INTER = "intermarche-05052"
API = "/api/drives"
RAPHAEL = ("raphael", "mot-de-passe-raphael-pour-les-tests")
ADAM = ("adam", "mot-de-passe-adam-pour-les-tests")
EDGE_RAPHAEL = {"X-Drives-Jeton": "jeton-collecte-raphael-pour-les-tests"}
EDGE_ADAM = {"X-Drives-Jeton": "jeton-collecte-adam-pour-les-tests"}


def autorisation(compte):
    return {"Authorization": "Basic " + base64.b64encode(":".join(compte).encode()).decode()}


def configurer(reglages):
    return reglages.model_copy(
        update={
            "site_partage_origine": ORIGINE,
            "site_partage_comptes": {
                nom: SecretStr(mot_de_passe) for nom, mot_de_passe in (RAPHAEL, ADAM)
            },
            "drives_collecteurs": {
                "edge-raphael": SecretStr(EDGE_RAPHAEL["X-Drives-Jeton"]),
                "edge-adam": SecretStr(EDGE_ADAM["X-Drives-Jeton"]),
            },
            "secret_key": "cle-de-session-unique-pour-le-site-partage-de-test",
            "magasins_osm": True,
            "drives_attente_s": 0,
            "mode_donnees_defaut": "reel",  # relevés Edge : mode « données réelles »
        }
    )


def demander(client, recherche="Nutella"):
    reponse = client.post(API + "/recherches", json={"q": recherche, "drives": [INTER]})
    assert reponse.status_code == 200
    return reponse.json()[0]


def test_site_partage_prix_persistant_panier_prive_et_releve_unique(reglages):
    reglages = configurer(reglages)
    app = creer_app(reglages)
    with (
        TestClient(app, base_url=ORIGINE, headers=autorisation(RAPHAEL)) as raphael,
        TestClient(app, base_url=ORIGINE, headers=autorisation(ADAM)) as adam,
        TestClient(app, base_url=ORIGINE, client=("192.0.2.90", 8900)) as navigateur,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        raphael.get("/magasins?code_postal=35170")
        adam.get("/magasins?code_postal=35170")
        ajout = raphael.post(
            "/panier/lignes", data={"mode": "equivalent", "recherche": "Nutella", "quantite": "1"}
        )
        assert ajout.status_code == 200
        assert "Nutella" in raphael.get("/panier").text
        assert "Nutella" not in adam.get("/panier").text
        assert "secure" in ajout.headers["set-cookie"].lower()

        demande_raphael = pool.submit(demander, raphael)
        demande_adam = pool.submit(demander, adam, " NUTELLA ")
        assert demande_raphael.result()["tache_id"] == demande_adam.result()["tache_id"]
        route_enseigne = f"{API}/enseignes/intermarche"
        assert (
            navigateur.post(route_enseigne + "/connexion", headers=EDGE_RAPHAEL).status_code == 204
        )
        tache = navigateur.post(route_enseigne + "/prendre", headers=EDGE_RAPHAEL).json()
        assert navigateur.post(f"{API}/{INTER}/prendre", headers=EDGE_ADAM).json() is None
        depot = {
            "drive_id": INTER,
            "bail": tache["bail"],
            "etat": "succes",
            "service_observe": "05052",
            "produits": [
                {
                    "produit": "Nutella 400 g",
                    "prix_eur": "3.20",
                    "url": "https://www.intermarche.com/produit/nutella",
                }
            ],
        }
        route = f"{API}/taches/{tache['id']}/depot"
        assert navigateur.post(route, json=depot).status_code == 401
        assert navigateur.post(route, headers=EDGE_ADAM, json=depot).status_code == 409
        assert navigateur.post(route, headers=EDGE_RAPHAEL, json=depot).status_code == 204
        assert navigateur.post(route, headers=EDGE_RAPHAEL, json=depot).status_code == 204
        assert demander(adam)["produits"][0]["prix_centimes"] == 320

    with TestClient(
        creer_app(reglages), base_url=ORIGINE, headers=autorisation(ADAM)
    ) as apres_redemarrage:
        prix = demander(apres_redemarrage)
        assert prix["etat"] == "recent" and prix["tache_id"] is None
        apres_redemarrage.get("/magasins?code_postal=35170")
        apres_redemarrage.post(
            "/panier/lignes", data={"mode": "equivalent", "recherche": "Nutella"}
        )
        flux = apres_redemarrage.get("/panier/prix/flux").text
        assert f"event: total-{INTER}" in flux
        assert 'data-centimes="320" data-complet="1"' in flux
        with db.connexion(reglages.db_path) as cnx:
            assert cnx.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0] == 1
            assert (
                cnx.execute(
                    "SELECT count(*) FROM drive_tache WHERE drive_id=?", (INTER,)
                ).fetchone()[0]
                == 1
            )


def test_site_partage_protege_le_site_et_revoque_jeton(reglages):
    reglages = configurer(reglages)
    del reglages.drives_collecteurs["edge-raphael"]
    with TestClient(creer_app(reglages), base_url=ORIGINE) as visiteur:
        assert visiteur.get("/").status_code == 401
        assert visiteur.get("/", headers=EDGE_ADAM).status_code == 401
        assert visiteur.get("http://comparateur-test.equipe.ts.net/").status_code == 400
        assert visiteur.get("https://autre.equipe.ts.net/", auth=ADAM).status_code == 400
        for enseigne in ("carrefour", "leclerc"):
            route = f"{API}/enseignes/{enseigne}/connexion"
            assert visiteur.post(route).status_code == 401
            assert visiteur.post(route, headers=EDGE_ADAM).status_code == 204
        assert visiteur.post(f"{API}/{INTER}/connexion", headers=EDGE_RAPHAEL).status_code == 401
        assert visiteur.post(f"{API}/{INTER}/connexion", auth=ADAM).status_code == 401
        assert visiteur.post(f"{API}/{INTER}/connexion", headers=EDGE_ADAM).status_code == 204
        catalogue = f"{API}/enseignes/coursesu/points-retrait"
        assert visiteur.post(catalogue, headers=EDGE_RAPHAEL).status_code == 401
        points = visiteur.post(catalogue, headers=EDGE_ADAM).json()
        assert any(point["id"] == "hyperu-guichen" for point in points)
        assert (
            visiteur.post(f"{API}/enseignes/coursesu/prendre", headers=EDGE_RAPHAEL).status_code
            == 401
        )
        assert (
            visiteur.post(
                API + "/recherches",
                auth=ADAM,
                headers={"Origin": "https://autre.example"},
                json={"q": "Nutella", "drives": [INTER]},
            ).status_code
            == 403
        )


def test_site_partage_tache_disponible_apres_deconnexion(reglages, monkeypatch):
    reglages = configurer(reglages)
    with TestClient(creer_app(reglages), base_url=ORIGINE, headers=autorisation(RAPHAEL)) as client:
        tache = demander(client)
        plus_tard = service.maintenant() + timedelta(hours=2)
        monkeypatch.setattr(service, "maintenant", lambda: plus_tard)
        reprise = client.post(f"{API}/{INTER}/prendre", headers=EDGE_ADAM).json()
        assert reprise["id"] == tache["tache_id"]


def test_site_partage_cree_sa_configuration_une_seule_fois(tmp_path):
    fichier = tmp_path / ".env.partage"
    premier = preparer(fichier, ORIGINE)
    contenu = fichier.read_bytes()
    second = preparer(fichier, ORIGINE)
    assert fichier.read_bytes() == contenu
    assert premier.drives_collecteurs == second.drives_collecteurs
    assert premier.db_path.parent.name == "partage"
    assert len(premier.secret_key) >= 32
