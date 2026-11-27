import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.drives import service
from app.drives.importer import importer
from app.drives.modeles import ProduitObserve
from app.main import creer_app

U = "coursesu-33315"
INTER = "intermarche-05052"
URL = "/api/drives"
JETON = {"X-Drives-Jeton": "test-edge"}


@pytest.fixture
def edge(reglages, monkeypatch):
    reglages.drives_jeton = JETON["X-Drives-Jeton"]
    maintenant = [datetime(2026, 11, 27, 19, tzinfo=UTC)]
    monkeypatch.setattr(service, "maintenant", lambda: maintenant[0])
    with TestClient(creer_app(reglages), client=("127.0.0.1", 9999)) as client:
        yield client, maintenant


def produit(drive=U, **champs):
    hote = "www.coursesu.com" if drive == U else "www.intermarche.com"
    return {
        "produit": "Lait Lactel demi-écrémé",
        "marque": "Lactel",
        "format": "1 L",
        "ean": "0304360041667",
        "id_produit_source": "bouteille",
        "url": f"https://{hote}/produit/bouteille",
        "prix_eur": "1,25",
        "prix_par_unite_eur": "1.2500",
        "unite": "L",
        "promos": "2e à −50 % avec la carte",
        **champs,
    }


def lancer(client, q="Lait Lactel 1 L", drives=(INTER, U)):
    reponse = client.post(URL + "/recherches", json={"q": q, "drives": drives})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


def suivre(client, q="Lait Lactel 1 L", drives=(INTER, U)):
    reponse = client.get(URL + "/suivi", params={"q": q, "drives": drives})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


def prendre(client, drive):
    reponse = client.post(f"{URL}/{drive}/prendre", headers=JETON)
    assert reponse.status_code == 200
    return reponse.json()


def depot(client, tache, **champs):
    drive = tache["drive_id"]
    return client.post(
        f"{URL}/taches/{tache['id']}/depot",
        headers=JETON,
        json={"drive_id": drive, "bail": tache["bail"], **champs},
    )


def succes(client, tache, *produits, service_observe=None):
    return depot(
        client,
        tache,
        etat="succes",
        service_observe=service_observe or tache["drive_id"].split("-")[1],
        produits=produits,
    )


def test_drives_prix_connu_et_collecte_concurrente(edge, reglages):
    client, _ = edge
    with db.connexion(reglages.db_path) as cnx:
        service.observer(cnx, INTER, ProduitObserve(**produit(INTER)), "2026-11-27", "CSV")
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lancer, client)
        b = pool.submit(lancer, client, " LAIT   LACTEL 1l ")
        premier, second = a.result(), b.result()
    inter, u = premier
    assert inter["etat"] == "recent" and inter["tache_id"] is None
    assert inter["produits"][0]["releve_le"] == "2026-11-27"
    assert u["etat"] == "attente" and not u["connecte"]
    assert second[1]["tache_id"] == u["tache_id"]
    assert prendre(client, INTER) is None
    tache = prendre(client, U)
    assert tache["id"] == u["tache_id"]
    assert suivre(client)[1]["etat"] == "cours"
    assert succes(client, tache, produit()).status_code == 204
    assert succes(client, tache, produit()).status_code == 204
    assert suivre(client)[1]["produits"][0]["prix_centimes"] == 125
    assert suivre(client)[1]["produits"][0]["correspondance"] == "ean"
    assert all(d["etat"] == "recent" for d in lancer(client))
    assert prendre(client, U) is None
    with db.connexion(reglages.db_path) as cnx:
        assert cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0] == 2


def test_drives_base_vide_sans_ean_et_affichage(edge):
    client, _ = edge
    reponse = client.post(
        "/drives",
        data={"q": "Lait Lactel", "drives": [INTER, U]},
        headers={"HX-Request": "true"},
    )
    assert reponse.status_code == 200
    assert "En attente de l’extension Edge" in reponse.text
    assert 'hx-trigger="load delay:2s"' in reponse.text
    for drive in (INTER, U):
        tache = prendre(client, drive)
        assert tache["requete"] == "Lait Lactel"
        assert (
            succes(
                client,
                tache,
                produit(drive, ean=""),
                produit(drive, ean="", id_produit_source="pack", format="6 × 1 L", prix_eur="7.99"),
            ).status_code
            == 204
        )
    suite = lancer(client, "Lait Lactel")
    assert all(d["etat"] == "recent" and len(d["produits"]) == 2 for d in suite)
    reponse = client.get(
        "/drives/suivi",
        params={"q": "Lait Lactel", "drives": INTER},
        headers={"HX-Request": "true"},
    )
    assert "6 × 1 L" in reponse.text and "1,25 €" in reponse.text and "7,99 €" in reponse.text
    assert "2e à −50 % avec la carte" in reponse.text
    assert "hx-trigger" not in reponse.text


def test_drives_expiration_erreurs_et_prix_ancien(edge, reglages):
    client, temps = edge
    with db.connexion(reglages.db_path) as cnx:
        service.observer(cnx, U, ProduitObserve(**produit()), "2026-11-24", "CSV")
    premiere = lancer(client, drives=(U,))[0]
    assert premiere["etat"] == "attente"
    assert premiere["produits"][0]["releve_le"] == "2026-11-24"
    assert premiere["produits"][0]["ancien"]
    tache = prendre(client, U)
    temps[0] += timedelta(minutes=2)
    assert suivre(client, drives=(U,))[0]["erreur"] == "delai"
    assert succes(client, tache, produit()).status_code == 409
    lancer(client, drives=(U,))
    suivante = prendre(client, U)
    assert suivante["id"] != tache["id"]
    assert depot(client, suivante, etat="echec", erreur="reseau").status_code == 204
    echec = suivre(client, drives=(U,))[0]
    assert echec["etat"] == "echec" and echec["erreur"] == "reseau"
    assert echec["produits"][0]["ancien"]

    lancer(client, drives=(U,))
    tache = prendre(client, U)
    assert (
        depot(client, tache, drive_id=INTER, etat="vide", service_observe="05052").status_code
        == 409
    )
    assert succes(client, tache, produit(), service_observe="05052").status_code == 204
    assert suivre(client, drives=(U,))[0]["erreur"] == "mauvais_drive"
    with db.connexion(reglages.db_path) as cnx:
        assert cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0] == 1

    lancer(client, drives=(U,))
    assert (
        depot(client, prendre(client, U), etat="vide", service_observe="33315").status_code == 204
    )
    assert lancer(client, drives=(U,))[0]["etat"] == "vide"
    assert prendre(client, U) is None
    temps[0] += timedelta(minutes=11)
    assert lancer(client, drives=(U,))[0]["etat"] == "attente"


@pytest.mark.parametrize("erreur", ["403", "429", "defi"])
def test_drives_pause_par_retrait(edge, erreur):
    client, temps = edge
    lancer(client, "pates")
    lancer(client, "lait", (U,))
    assert depot(client, prendre(client, U), etat="echec", erreur=erreur).status_code == 204
    assert prendre(client, U) is None
    assert lancer(client, "farine", (U,))[0]["etat"] == "pause"
    assert prendre(client, INTER)
    temps[0] += timedelta(minutes=15)
    assert lancer(client, "lait", (U,))[0]["etat"] == "attente"


def test_drives_import_et_ean_en_texte(edge, reglages, tmp_path: Path):
    client, _ = edge
    chemin = tmp_path / "historique.csv"
    contenu = {
        **produit(INTER),
        "drive": "Intermarché Super Bruz Cap Vert",
        "service_drive": "05052",
        "releve_le": "2026-11-27",
    }
    assert service.ean_valide(contenu["ean"])
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.DictWriter(fichier, contenu.keys(), delimiter=";")
        writer.writeheader()
        writer.writerow(contenu)
    assert importer(reglages.db_path, chemin) == (1, 1)
    assert importer(reglages.db_path, chemin) == (1, 0)
    resultat = lancer(client, contenu["ean"], (INTER,))[0]["produits"][0]
    assert resultat["ean"] == contenu["ean"]
    assert resultat["releve_le"] == "2026-11-27"
    assert resultat["prix_par_unite_eur"] == "1.25"


def test_drives_refuse_collecteur_sans_jeton_et_internet(edge, reglages):
    client, _ = edge
    assert client.post(f"{URL}/{U}/prendre").status_code == 401
    with TestClient(creer_app(reglages)) as distant:
        assert distant.post(f"{URL}/{U}/prendre", headers=JETON).status_code == 403


def test_drives_rejette_un_lot_partiellement_invalide(edge, reglages):
    client, _ = edge
    lancer(client, drives=(U,))
    tache = prendre(client, U)
    assert succes(client, tache, produit(), produit(INTER)).status_code == 422
    with db.connexion(reglages.db_path) as cnx:
        assert cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0] == 0
    assert suivre(client, drives=(U,))[0]["etat"] == "cours"
    assert depot(client, tache, etat="echec", erreur="page_inattendue").status_code == 204


def test_drives_conditionnement_precis_et_correspondance_possible(edge):
    client, _ = edge
    lancer(client, "lait lactel 1 L")
    for drive in (INTER, U):
        assert (
            succes(
                client,
                prendre(client, drive),
                produit(drive, ean="", id_produit_source="pack", format="6x1L"),
                produit(drive, ean=""),
            ).status_code
            == 204
        )
    for drive in lancer(client, "lait lactel 1 L"):
        bouteille, pack = drive["produits"]
        assert bouteille["format"] == "1 L"
        assert pack["format"] == "6x1L"
        assert bouteille["correspondance"] == pack["correspondance"] == "possible"
