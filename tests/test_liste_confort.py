"""Confort de la liste : quantités, vider, « Annuler », reprise depuis l'accueil et les magasins."""

import json
import re
from html import unescape

NUTELLA = "3017620422003"


def _liste_avec_deux_articles(client) -> list[str]:
    client.get("/magasins", params={"code_postal": "35170"})
    client.post(
        "/panier/lignes",
        data={
            "mode": "produit",
            "ean": NUTELLA,
            "recherche": "nutella",
            "libelle": "Nutella 400 g",
        },
    )
    page = client.post(
        "/panier/lignes", data={"mode": "equivalent", "recherche": "riz", "quantite": "2"}
    ).text
    return re.findall(r'data-id="(\d+)"', page)


def test_quantite_entre_1_et_99(client):
    nutella, riz = _liste_avec_deux_articles(client)
    page = client.post(f"/panier/lignes/{riz}/quantite", data={"quantite": "3"}).text
    assert "3×" in page
    page = client.post(f"/panier/lignes/{riz}/quantite", data={"quantite": "0"}).text
    assert "3×" in page  # refusé : on garde 3
    # À 1, le bouton « − » est désactivé.
    page = client.post(f"/panier/lignes/{nutella}/quantite", data={"quantite": "1"}).text
    assert f'hx-post="/panier/lignes/{nutella}/quantite" hx-vals=\'{{"quantite": 0}}\'' not in page


def test_retirer_puis_annuler_remet_l_article_a_sa_place(client):
    nutella, riz = _liste_avec_deux_articles(client)
    page = client.delete(f"/panier/lignes/{nutella}").text
    assert "« Nutella 400 g » retiré." in page and "Annuler" in page
    assert 'hx-swap-oob="beforeend:#toasts"' in page
    lignes = re.search(r"hx-vals='(.*?)'", page.split('class="toast"')[1])[1]
    donnees = json.loads(json.loads(lignes)["lignes"])
    assert donnees[0]["ean"] == NUTELLA

    page = client.post("/panier/lignes/restaurer", data={"lignes": json.dumps(donnees)}).text
    assert "Article remis dans la liste." in page
    assert re.findall(r'data-id="(\d+)"', page) == [nutella, riz]  # même place qu'avant


def test_vider_puis_annuler(client):
    _liste_avec_deux_articles(client)
    page = client.post("/panier/lignes/vider").text
    assert "Votre liste est vide" in page and "Liste vidée (2 articles)." in page
    vals = json.loads(re.search(r"hx-vals='(.*?)'", page.split('class="toast"')[1])[1])
    page = client.post("/panier/lignes/restaurer", data=vals).text
    assert "2 articles remis." in page and "Nutella 400 g" in page and "riz" in page


def test_annuler_ignore_les_donnees_invalides(client):
    _liste_avec_deux_articles(client)
    mauvais = json.dumps([{"id": 1, "mode": "produit", "recherche": "x"}, {"n'importe": "quoi"}])
    page = client.post("/panier/lignes/restaurer", data={"lignes": mauvais}).text
    assert "remis" not in page
    assert (
        client.post("/panier/lignes/restaurer", data={"lignes": "pas du json"}).status_code == 200
    )


def test_reprendre_sa_liste_depuis_l_accueil_et_les_magasins(client):
    assert "Reprendre ma liste" not in client.get("/").text
    _liste_avec_deux_articles(client)
    assert "Reprendre ma liste" in client.get("/").text
    page = client.get("/magasins", params={"code_postal": "35170"}).text
    assert "Voir ma liste (2 articles)" in page and "comparer=1" not in page


def test_la_comparaison_ne_part_que_sur_clic(client):
    _liste_avec_deux_articles(client)
    # Même avec un ancien lien « ?comparer=1 », rien ne se lance et la page ne défile pas toute seule.
    for page in (client.get("/panier").text, client.get("/panier?comparer=1").text):
        assert '<section id="resultats" aria-label="Comparaison des prix"></section>' in page
        assert 'hx-trigger="load"' not in page
        assert page.count('hx-get="/panier/resultats"') == 1  # le bouton « Comparer les prix »
    assert "comparer=1" not in client.get("/").text


def _total(numero: str, centimes: int, manquants: int):
    from app.contrats import Enseigne, Magasin, Position, TotalMagasin

    magasin = Magasin(
        id=f"carrefour-{numero}",
        enseigne=Enseigne.CARREFOUR,
        id_enseigne=numero,
        nom=f"Magasin {numero}",
        position=Position(lat=48.0, lon=-1.7),
        distance_km=0.6,
    )
    return TotalMagasin(
        magasin=magasin,
        total_centimes=centimes,
        economies_centimes=0,
        nb_trouves=3,
        nb_manquants=manquants,
        complet=manquants == 0,
    )


def test_meilleur_magasin_nom_total_et_economie_seulement():
    from app.gabarits import rendre

    totaux = [_total("1", 4073, 1), _total("2", 4200, 1)]
    html = rendre("panier/_resume.html", totaux=totaux, gain=127)
    carte = html.split('<ol class="classement"')[0]
    texte = " ".join(unescape(re.sub(r"<[^>]+>", " ", carte)).split())
    assert texte == "Magasin 1 40 ,73 € 1,27 € économisés"
    assert 'data-gagnant="carrefour-1"' in carte and 'data-centimes="4073"' in carte
    assert "1 manquant" in html  # reste signalé dans le classement


def test_meilleur_magasin_sans_economie_comparable():
    from app.gabarits import rendre

    html = rendre("panier/_resume.html", totaux=[_total("1", 4073, 1)], gain=0)
    assert "économisé" not in html


def test_resultats_sous_le_tableau_des_prix(client):
    _liste_avec_deux_articles(client)
    page = client.get("/panier/resultats").text
    assert page.index('class="tableau-prix"') < page.index('sse-swap="resume"')
