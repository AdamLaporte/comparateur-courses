import cv2
import numpy as np

from app.panier import ticket

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
    page = client.post("/panier/ticket", files={"image": ("t.jpg", b"jpeg", "image/jpeg")})
    assert 'value="nutella 400 g"' in page.text and "Ajouter à ma liste" in page.text
    assert "lait demi-écrémé" not in client.get("/panier/resultats").text  # rien d'ajouté encore

    # L'utilisateur retire le lait (champ vidé) et corrige la quantité des pâtes.
    page = client.post(
        "/panier/ticket/ajouter",
        data={"recherche": ["nutella 400 g", "", "pâtes spaghetti"], "quantite": ["1", "1", "3"]},
    )
    assert "nutella 400 g" in page.text and "pâtes spaghetti" in page.text
    assert "lait demi-écrémé" not in page.text
    assert "3×" in page.text and 'id="ticket-lu" hx-swap-oob="true"' in page.text


def test_ticket_quantite_invalide_signalee(client):
    page = client.post("/panier/ticket/ajouter", data={"recherche": ["lait"], "quantite": ["500"]})
    assert "1 article(s) non ajouté(s)" in page.text


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
