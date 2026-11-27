"""Comptes facultatifs : inscription, connexion, déconnexion, mot de passe perdu, changement."""

import re
import sqlite3

import pytest

from app.comptes import service

EMAIL = "etudiant@example.org"
MDP = "un-bon-mot-de-passe"


@pytest.fixture(autouse=True)
def _remettre_a_zero():
    service._echecs.clear()
    yield
    service._echecs.clear()


@pytest.fixture
def liens(monkeypatch):
    """Capture les liens de réinitialisation au lieu de les envoyer."""
    envoyes: list[tuple[str, str]] = []

    async def capturer(reglages, email, lien):
        envoyes.append((email, lien))

    monkeypatch.setattr(service, "envoyer_lien", capturer)
    return envoyes


def _inscrire(client, email=EMAIL, mdp=MDP, confirmation=None):
    return client.post(
        "/comptes/inscription",
        data={"email": email, "mot_de_passe": mdp, "confirmation": confirmation or mdp},
    )


def _connecter(client, email=EMAIL, mdp=MDP, suivant="/comptes"):
    return client.post(
        "/comptes/connexion", data={"email": email, "mot_de_passe": mdp, "suivant": suivant}
    )


def _chemin(lien: str) -> str:
    return re.sub(r"^https?://[^/]+", "", lien)


def test_site_utilisable_sans_compte(client):
    assert client.get("/").status_code == 200
    page = client.get("/comptes")
    assert page.status_code == 200
    assert "facultatif" in page.text
    assert "Se connecter" in page.text


def test_inscription_connecte_et_hache(client, reglages):
    reponse = _inscrire(client, email="  Etudiant@Example.ORG ")
    assert reponse.status_code == 200
    assert "Compte créé" in reponse.text
    assert EMAIL in reponse.text  # e-mail normalisé
    assert "Mon compte" in reponse.text

    with sqlite3.connect(reglages.db_path) as cnx:
        (hachage,) = cnx.execute("SELECT mot_de_passe_hash FROM utilisateur").fetchone()
    assert hachage.startswith("$argon2") and MDP not in hachage


@pytest.mark.parametrize(
    ("email", "mdp", "confirmation", "message"),
    [
        ("pas-un-email", MDP, MDP, "e-mail invalide"),
        (EMAIL, "court", "court", "au moins 8"),
        (EMAIL, MDP, MDP + "x", "pas identiques"),
    ],
)
def test_inscription_refusee(client, email, mdp, confirmation, message):
    reponse = _inscrire(client, email, mdp, confirmation)
    assert reponse.status_code == 400
    assert message in reponse.text
    assert "Traceback" not in reponse.text


def test_email_deja_pris(client):
    _inscrire(client)
    client.post("/comptes/deconnexion")
    reponse = _inscrire(client)
    assert reponse.status_code == 400
    assert "existe déjà" in reponse.text


def test_connexion_et_deconnexion(client):
    _inscrire(client)
    page = client.post("/comptes/deconnexion")
    assert "déconnecté" in page.text and "Se connecter" in page.text

    assert _connecter(client, mdp="mauvais-mot-de-passe").status_code == 400
    assert _connecter(client, email="inconnu@example.org").status_code == 400
    reponse = _connecter(client, email="ETUDIANT@example.org")
    assert reponse.status_code == 200 and EMAIL in reponse.text


def test_meme_message_email_inconnu_ou_mauvais_mot_de_passe(client):
    _inscrire(client)
    client.post("/comptes/deconnexion")
    inconnu = _connecter(client, email="inconnu@example.org").text
    mauvais = _connecter(client, mdp="mauvais-mot-de-passe").text
    assert "E-mail ou mot de passe incorrect." in inconnu
    assert "E-mail ou mot de passe incorrect." in mauvais


def test_trop_d_essais(client):
    _inscrire(client)
    client.post("/comptes/deconnexion")
    for _ in range(service.MAX_ECHECS):
        _connecter(client, mdp="mauvais-mot-de-passe")
    reponse = _connecter(client)  # même le bon mot de passe est refusé un moment
    assert reponse.status_code == 400 and "Trop d&#39;essais" in reponse.text


def test_redirection_apres_connexion_seulement_sur_le_site(client):
    _inscrire(client)
    client.post("/comptes/deconnexion")
    reponse = client.post(
        "/comptes/connexion",
        data={"email": EMAIL, "mot_de_passe": MDP, "suivant": "//pirate.example.org/"},
        follow_redirects=False,
    )
    assert reponse.headers["location"] == "/comptes"


def test_la_liste_sans_compte_est_gardee_a_la_connexion(client):
    client.get("/magasins", params={"code_postal": "35170"})
    client.post("/panier/lignes", data={"mode": "equivalent", "recherche": "cornichons extra-fins"})
    _inscrire(client)
    assert "cornichons extra-fins" in client.get("/panier").text

    # Déconnecté : nouvelle liste vide ; reconnecté : la liste revient.
    client.post("/comptes/deconnexion")
    assert "cornichons extra-fins" not in client.get("/panier").text
    _connecter(client)
    assert "cornichons extra-fins" in client.get("/panier").text


def test_mot_de_passe_perdu(client, liens):
    _inscrire(client)
    client.post("/comptes/deconnexion")

    # Même réponse pour une adresse inconnue, et aucun lien envoyé.
    inconnu = client.post("/comptes/mot-de-passe-perdu", data={"email": "inconnu@example.org"})
    assert "Si un compte existe" in inconnu.text and liens == []

    reponse = client.post("/comptes/mot-de-passe-perdu", data={"email": EMAIL})
    assert "Si un compte existe" in reponse.text
    assert len(liens) == 1 and liens[0][0] == EMAIL
    chemin = _chemin(liens[0][1])
    jeton = chemin.split("jeton=")[1]

    assert client.get(chemin).status_code == 200
    nouveau = "un-nouveau-mot-de-passe"
    page = client.post(
        "/comptes/reinitialiser", data={"jeton": jeton, "nouveau": nouveau, "confirmation": nouveau}
    )
    assert "Mot de passe enregistré" in page.text  # et connecté

    client.post("/comptes/deconnexion")
    assert _connecter(client, mdp=MDP).status_code == 400  # l'ancien ne marche plus
    assert _connecter(client, mdp=nouveau).status_code == 200

    # Le lien ne sert qu'une fois.
    deja = client.post(
        "/comptes/reinitialiser",
        data={"jeton": jeton, "nouveau": "encore-un-autre", "confirmation": "encore-un-autre"},
    )
    assert deja.status_code == 400 and "déjà servi" in deja.text


def test_lien_falsifie_ou_expire(client, liens, reglages, monkeypatch):
    assert (
        client.get("/comptes/reinitialiser", params={"jeton": "n-importe-quoi"}).status_code == 400
    )

    _inscrire(client)
    client.post("/comptes/mot-de-passe-perdu", data={"email": EMAIL})
    jeton = liens[0][1].split("jeton=")[1]
    monkeypatch.setattr(service, "DUREE_LIEN_S", -1)
    page = client.get("/comptes/reinitialiser", params={"jeton": jeton})
    assert page.status_code == 400 and "expiré" in page.text


def test_lien_ecrit_dans_le_journal_sans_smtp(client, caplog):
    _inscrire(client)
    with caplog.at_level("WARNING"):
        client.post("/comptes/mot-de-passe-perdu", data={"email": EMAIL})
    assert "comptes/reinitialiser?jeton=" in caplog.text


def test_changer_de_mot_de_passe(client):
    assert "Se connecter" in client.get("/comptes/mot-de-passe").text  # connexion demandée
    _inscrire(client)
    nouveau = "un-nouveau-mot-de-passe"
    refuse = client.post(
        "/comptes/mot-de-passe",
        data={"actuel": "mauvais-mot-de-passe", "nouveau": nouveau, "confirmation": nouveau},
    )
    assert refuse.status_code == 400 and "actuel incorrect" in refuse.text
    ok = client.post(
        "/comptes/mot-de-passe", data={"actuel": MDP, "nouveau": nouveau, "confirmation": nouveau}
    )
    assert "Mot de passe enregistré" in ok.text
    client.post("/comptes/deconnexion")
    assert _connecter(client, mdp=nouveau).status_code == 200


# --- Articles favoris ---


def _ligne_dans_la_liste(client, recherche="cornichons extra-fins", **champs):
    client.get("/magasins", params={"code_postal": "35170"})
    client.post("/panier/lignes", data={"mode": "equivalent", "recherche": recherche, **champs})


def _ids_lignes(client) -> list[int]:
    return [
        int(i)
        for i in re.findall(r"/comptes/favoris/depuis-ligne/(\d+)", client.get("/panier").text)
    ]


def test_bouton_favori_seulement_si_connecte(client):
    _ligne_dans_la_liste(client)
    assert "☆ Favori" not in client.get("/panier").text
    _inscrire(client)
    assert "☆ Favori" in client.get("/panier").text


def test_favori_depuis_la_liste_puis_vers_la_liste(client):
    _inscrire(client)
    _ligne_dans_la_liste(client)
    client.post(
        "/panier/lignes",
        data={
            "mode": "produit",
            "ean": "3017620422003",
            "recherche": "nutella",
            "libelle": "Nutella 400 g",
        },
    )
    for ligne_id in _ids_lignes(client):
        assert "★ En favori" in client.post(f"/comptes/favoris/depuis-ligne/{ligne_id}").text
        client.post(f"/comptes/favoris/depuis-ligne/{ligne_id}")  # deuxième clic : pas de doublon

    page = client.get("/comptes/favoris").text
    assert page.count("Ajouter à ma liste") == 2
    assert "Nutella 400 g" in page and "cornichons extra-fins" in page

    # On vide la liste, puis on la reconstruit depuis les favoris.
    for ligne_id in _ids_lignes(client):
        client.delete(f"/panier/lignes/{ligne_id}")
    assert _ids_lignes(client) == []
    reponse = client.post("/comptes/favoris/tout-ajouter")
    assert "Nutella 400 g" in reponse.text and "cornichons extra-fins" in reponse.text
    assert len(_ids_lignes(client)) == 2


def test_retirer_un_favori_et_favoris_prives(client):
    _inscrire(client)
    _ligne_dans_la_liste(client)
    client.post(f"/comptes/favoris/depuis-ligne/{_ids_lignes(client)[0]}")
    favori_id = re.search(r"/comptes/favoris/(\d+)/supprimer", client.get("/comptes/favoris").text)[
        1
    ]
    client.post("/comptes/deconnexion")

    # Un autre compte ne voit ni ne supprime les favoris du premier.
    _inscrire(client, email="autre@example.org")
    assert "cornichons" not in client.get("/comptes/favoris").text
    client.post(f"/comptes/favoris/{favori_id}/supprimer")
    client.post("/comptes/deconnexion")

    _connecter(client)
    assert "cornichons" in client.get("/comptes/favoris").text
    client.post(f"/comptes/favoris/{favori_id}/supprimer")
    assert "Aucun favori" in client.get("/comptes/favoris").text


def test_favoris_demandent_une_connexion(client):
    assert "Se connecter" in client.get("/comptes/favoris").text
    assert "Connectez-vous" in client.post("/comptes/favoris/depuis-ligne/1").text


# --- Maison ---


def test_maison(client):
    assert "🏠 Maison" not in client.get("/").text
    _inscrire(client)
    page = client.post("/comptes/maison", data={"code_postal": "35170"})
    assert "Maison enregistrée" in page.text and "35170 Bruz" in page.text

    # Proposée sur l'accueil, et reconnue sur la page des magasins.
    assert "🏠 Maison · 35170 Bruz" in client.get("/").text
    assert "C'est votre maison" in client.get("/magasins", params={"code_postal": "35170"}).text

    # Reconnexion : la maison revient et sert de code postal par défaut.
    client.post("/comptes/deconnexion")
    client.cookies.clear()
    _connecter(client)
    assert "🏠 Maison · 35170 Bruz" in client.get("/").text
    assert (
        client.get("/panier", follow_redirects=False).status_code == 200
    )  # code postal déjà connu

    client.post("/comptes/maison/supprimer")
    assert "🏠 Maison" not in client.get("/").text


def test_maison_depuis_la_page_des_magasins(client):
    _inscrire(client)
    page = client.get("/magasins", params={"code_postal": "35170"})
    assert "Enregistrer comme maison" in page.text
    reponse = client.post(
        "/comptes/maison",
        data={"code_postal": "35170", "suivant": "/magasins?code_postal=35170"},
        follow_redirects=False,
    )
    assert reponse.headers["location"] == "/magasins?code_postal=35170"


def test_maison_code_postal_refuse(client):
    _inscrire(client)
    page = client.post("/comptes/maison", data={"code_postal": "abc"})
    assert page.status_code == 400 and "5 chiffres" in page.text
    assert client.post("/comptes/deconnexion").status_code == 200
    assert "Se connecter" in client.post("/comptes/maison", data={"code_postal": "35170"}).text
