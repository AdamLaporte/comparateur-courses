"""Parcours principal avec les données fictives :
code postal → magasins → liste de courses → prix et total par magasin."""

import re

from app.contrats import Enseigne, StatutPrix, TotauxReponse

NUTELLA = "3017620422003"


def test_magasins_proches_json(client):
    reponse = client.get("/api/magasins", params={"code_postal": "35170"})
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["ville"] == "Bruz"
    magasins = donnees["magasins"]
    # 2 magasins par enseigne (MAX_MAGASINS_PAR_ENSEIGNE), triés par distance.
    assert len(magasins) == 8
    assert {m["enseigne"] for m in magasins} == {e.value for e in Enseigne}
    distances = [m["distance_km"] for m in magasins]
    assert distances == sorted(distances)
    assert all(m["est_fictif"] for m in magasins)


def test_code_postal_invalide_sans_erreur_brute(client):
    assert client.get("/api/magasins", params={"code_postal": "123"}).status_code == 422
    page = client.get("/magasins", params={"code_postal": "123"})
    assert page.status_code == 200
    assert "5 chiffres" in page.text
    assert "Traceback" not in page.text


def test_totaux_par_magasin_json(client):
    demande = {
        "code_postal": "35170",
        "lignes": [
            {"mode": "produit", "ean": NUTELLA, "recherche": "nutella", "quantite": 2},
            {"mode": "equivalent", "recherche": "lait demi-écrémé"},
        ],
    }
    reponse = client.post("/api/panier/totaux", json=demande)
    assert reponse.status_code == 200
    totaux = TotauxReponse.model_validate(reponse.json())

    assert len(totaux.magasins) == 8
    assert len(totaux.resultats) == 2 * 8  # une réponse par (ligne, magasin)
    assert len(totaux.totaux) == 8
    assert [t.rang for t in totaux.totaux] == list(range(1, 9))

    for total in totaux.totaux:
        siens = [r for r in totaux.resultats if r.magasin_id == total.magasin.id]
        trouves = [r for r in siens if r.statut == StatutPrix.TROUVE]
        assert total.total_centimes == sum(r.sous_total_centimes for r in trouves)
        assert total.nb_trouves + total.nb_manquants == 2
    for resultat in totaux.resultats:
        if resultat.prix is not None:
            # Chaque prix indique sa source et l'heure du relevé, et le fictif est marqué.
            assert resultat.prix.est_fictif
            assert resultat.prix.source_detail == "Données fictives"
            assert resultat.prix.releve_le is not None


def test_parcours_html_et_flux_sse(client):
    accueil = client.get("/")
    assert accueil.status_code == 200
    assert 'name="code_postal"' in accueil.text

    page = client.get("/magasins", params={"code_postal": "35170"})
    assert page.status_code == 200
    assert page.text.count('class="badge') >= 8

    suggestions = client.get("/produits/recherche", params={"q": "nutella"})
    assert NUTELLA in suggestions.text

    ajout = client.post(
        "/panier/lignes",
        data={
            "mode": "produit",
            "ean": NUTELLA,
            "recherche": "nutella",
            "libelle": "Nutella 400 g",
        },
    )
    assert "Nutella 400 g" in ajout.text
    ajout = client.post(
        "/panier/lignes", data={"mode": "equivalent", "recherche": "spaghetti", "quantite": "3"}
    )
    assert "spaghetti" in ajout.text

    tableau = client.get("/panier/resultats")
    assert 'sse-connect="/panier/prix/flux"' in tableau.text
    assert tableau.text.count('sse-swap="prix-') == 2 * 8

    with client.stream("GET", "/panier/prix/flux") as flux:
        assert flux.headers["content-type"].startswith("text/event-stream")
        texte = "".join(flux.iter_text())
    assert texte.count("event: prix-") == 2 * 8
    assert texte.count("event: total-") == 2 * 8
    assert "event: resume" in texte
    assert texte.rstrip().endswith("data: fin")
    assert "Données fictives" in texte


def test_suppression_de_ligne(client):
    client.get("/magasins", params={"code_postal": "35170"})
    client.post("/panier/lignes", data={"mode": "equivalent", "recherche": "riz"})
    page = client.get("/panier")
    assert "riz" in page.text
    ligne_id = page.text.split('hx-delete="/panier/lignes/')[1].split('"')[0]
    reponse = client.delete(f"/panier/lignes/{ligne_id}")
    assert "Votre liste est vide" in reponse.text


def test_pages_annexes(client):
    assert client.get("/comptes").status_code == 200
    absente = client.get("/page-qui-n-existe-pas")
    assert absente.status_code == 404
    assert "Oups" in absente.text


def test_sources_reelles_pas_encore_branchees(reglages, monkeypatch):
    """Carrefour en collecte (bouchon) et Intermarché en API sans clé : le site reste utilisable,
    sans requête réseau ni erreur brute ; ces enseignes sont signalées sans magasin."""
    from fastapi.testclient import TestClient

    from app.main import creer_app

    async def requete_interdite(*args, **kwargs):
        raise AssertionError("aucune requête HTTP attendue")

    monkeypatch.setattr("httpx.AsyncClient.send", requete_interdite)
    reglages.source_carrefour = "collecte"
    reglages.source_intermarche = "api"
    with TestClient(creer_app(reglages)) as client:
        donnees = client.get("/api/magasins", params={"code_postal": "35170"}).json()
        assert {m["enseigne"] for m in donnees["magasins"]} == {"leclerc", "coursesu"}
        assert set(donnees["enseignes_sans_magasin"]) == {"carrefour", "intermarche"}
        page = client.get("/magasins", params={"code_postal": "35170"})
        assert "Pas de magasin trouvé pour" in page.text


def test_basculer_un_article_et_toute_la_liste_au_moins_cher(client):
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
    client.post("/panier/lignes", data={"mode": "equivalent", "recherche": "riz"})
    page = client.get("/panier").text
    nutella_id = re.search(r"/panier/lignes/(\d+)/mode", page)[1]
    assert "Tout passer au moins cher" in page

    # Un article au moins cher : il garde son EAN pour pouvoir revenir au produit choisi.
    page = client.post(f"/panier/lignes/{nutella_id}/mode", data={"mode": "equivalent"}).text
    assert "Le moins cher pour « nutella »" in page and "Revenir aux produits choisis" in page
    page = client.post(f"/panier/lignes/{nutella_id}/mode", data={"mode": "produit"}).text
    assert "Le moins cher pour « nutella »" not in page

    # Toute la liste, puis retour.
    page = client.post("/panier/lignes/mode", data={"mode": "equivalent"}).text
    assert "Tout passer au moins cher" not in page and "Revenir aux produits choisis" in page
    page = client.post("/panier/lignes/mode", data={"mode": "produit"}).text
    assert "Tout passer au moins cher" in page

    # Le riz n'a pas d'EAN : il ne peut pas devenir « produit précis ».
    riz_id = int(nutella_id) + 1
    page = client.post(f"/panier/lignes/{riz_id}/mode", data={"mode": "produit"}).text
    assert (
        f"/panier/lignes/{riz_id}/mode" not in page and "Article ajouté sans produit précis" in page
    )
