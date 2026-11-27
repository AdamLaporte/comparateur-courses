import cv2
import numpy as np

from app.panier import ticket

NUTELLA = "3017620422003"

LIGNES = [
    "CARREFOUR MARKET",
    "NUTELLA400G 3,49",
    "LT1/2ECRUHT1L 0,95",
    "PATESSPAGHETTI 2,40",
    "2x1,20",
    "REMISE FIDELITE -0,50",
    "TOTAL 6,34",
    "CB 6,34",
    "MERCI CHIPS 1,00",
]


def test_analyser_garde_les_articles_et_les_quantites():
    assert ticket.analyser(LIGNES) == [
        ("nutella 400 g", 1),
        ("lait demi-écrémé 1 l", 1),
        ("pâtes spaghetti", 2),
    ]


def test_ticket_lu_puis_ajoute_apres_verification(client, monkeypatch):
    monkeypatch.setattr(ticket, "lire_texte", lambda image: LIGNES)
    client.get("/magasins", params={"code_postal": "35170"})
    page = client.post("/panier/ticket", files={"image": ("t.jpg", b"jpeg", "image/jpeg")})
    assert 'value="nutella 400 g"' in page.text and "Ajouter à ma liste" in page.text
    # Chaque article est rapproché d'un produit vendu en magasin (catalogue fictif dans les tests).
    assert f'value="{NUTELLA}|' in page.text
    assert "lait demi-écrémé" not in client.get("/panier/resultats").text  # rien d'ajouté encore

    # L'utilisateur retire le lait (champ vidé), garde le Nutella proposé et corrige les pâtes.
    page = client.post(
        "/panier/ticket/ajouter",
        data={
            "recherche": ["nutella 400 g", "", "pâtes spaghetti"],
            "quantite": ["1", "1", "3"],
            "choix": [f"{NUTELLA}|Nutella 400 g", "inexistant", "inexistant"],
        },
    )
    assert "Nutella 400 g" in page.text and "pâtes spaghetti" in page.text
    assert "lait demi-écrémé" not in page.text
    assert "3×" in page.text and 'id="ticket-lu" hx-swap-oob="true"' in page.text
    assert "produit précis" in page.text and "inexistant en magasins" in page.text


def test_article_inexistant_cherche_sur_le_drive(client, reglages):
    """Un article absent du catalogue est cherché sur le drive de Bruz : ici l'extension l'a déjà
    relevé sur l'Intermarché, donc le prix s'affiche dans la case de ce magasin."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app import db
    from app.drives.modeles import ProduitObserve
    from app.drives.service import observer

    reglages.drives_jeton = "j" * 32
    reglages.mode_donnees_defaut = "reel"  # relevés Edge : mode « données réelles »
    reglages.drives_attente_s = 0
    reglages.magasins_osm = True
    client.get("/magasins", params={"code_postal": "35170", "rayon_km": "5"})  # drives de Bruz
    client.post(
        "/panier/ticket/ajouter",
        data={"recherche": ["xyzqwertyu"], "quantite": ["1"], "choix": ["inexistant"]},
    )
    with db.connexion(reglages.db_path) as cnx:
        produit = ProduitObserve(
            produit="Xyzqwertyu nature",
            prix_eur=Decimal("2.49"),
            url="https://www.intermarche.com/produit/xyzqwertyu/123",
        )
        observer(cnx, "intermarche-05052", produit, datetime.now(UTC).isoformat(), "extension")

    tableau = client.get("/panier/resultats").text
    assert "hors catalogue" in tableau and 'sse-swap="prix-1-intermarche-05052"' in tableau
    with client.stream("GET", "/panier/prix/flux") as flux:
        texte = "".join(flux.iter_text())
    assert "event: prix-1-intermarche-05052" in texte and "2,49 €" in texte
    assert texte.rstrip().endswith("data: fin")


def test_ticket_quantite_invalide_signalee(client):
    page = client.post(
        "/panier/ticket/ajouter",
        data={"recherche": ["lait"], "quantite": ["500"], "choix": ["inexistant"]},
    )
    assert "1 article(s) non ajouté(s)" in page.text


def test_nouvelles_correspondances_apres_correction(client):
    page = client.get("/panier/ticket/correspondances", params={"recherche": "nutella", "n": 2})
    assert 'id="ticket-choix-2"' in page.text and f'value="{NUTELLA}|' in page.text


def test_decoupage_des_mots_colles():
    assert ticket.nettoyer("CREMEFRAICHE") == "crème fraîche"
    assert ticket.nettoyer("BEURREDOUX250G") == "beurre doux 250 g"
    assert ticket.nettoyer("XYZQWERTYU") == "xyzqwertyu"  # inconnu : gardé tel quel


def test_ticket_refuse_ce_qui_n_est_pas_une_image(client):
    page = client.post("/panier/ticket", files={"image": ("t.txt", b"texte", "text/plain")})
    assert "photo du ticket" in page.text


def test_lecture_reelle_d_une_image():
    lignes = ["NUTELLA 400G        3,49", "OEUFS X12           3,10", "TOTAL               6,59"]
    image = np.full((60 + 45 * len(lignes), 700, 3), 255, np.uint8)
    for i, ligne in enumerate(lignes):
        cv2.putText(image, ligne, (20, 50 + 45 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    texte = ticket.lire_texte(cv2.imencode(".png", image)[1].tobytes())
    assert [r for r, _ in ticket.analyser(texte)][0].startswith("nutella")


def test_sans_releve_une_recherche_est_demandee_a_l_extension(client, reglages):
    from app import db

    reglages.drives_jeton = "j" * 32
    reglages.mode_donnees_defaut = "reel"  # relevés Edge : mode « données réelles »
    reglages.drives_attente_s = 0  # l'extension ne répond pas à temps : la case retombe proprement
    reglages.magasins_osm = True
    client.get("/magasins", params={"code_postal": "35170", "rayon_km": "5"})  # drives de Bruz
    client.post(
        "/panier/ticket/ajouter",
        data={"recherche": ["xyzqwertyu"], "quantite": ["1"], "choix": ["inexistant"]},
    )
    with client.stream("GET", "/panier/prix/flux") as flux:
        texte = "".join(flux.iter_text())
    assert "Recherche sur le drive Intermarché Super Bruz Cap Vert" in texte
    assert texte.rstrip().endswith("data: fin")
    with db.connexion(reglages.db_path) as cnx:
        taches = cnx.execute("SELECT drive_id, requete, etat FROM drive_tache").fetchall()
    assert {tuple(tache) for tache in taches} == {
        ("coursesu-33315", "xyzqwertyu", "attente"),
        ("intermarche-05052", "xyzqwertyu", "attente"),
    }
