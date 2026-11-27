"""Relevés des drives dans la comparaison : textes de promo lisibles, même produit sous un autre EAN."""

from datetime import UTC, datetime
from decimal import Decimal

from app import db
from app.contrats import LigneListe, ModeLigne
from app.drives.comparaison import _meme_produit_par_nom, nettoyer_promo
from app.drives.modeles import ProduitObserve
from app.drives.service import observer


def test_promo_super_u_sans_code_de_campagne_ni_html():
    brut = (
        "TRAFIC S47-48 - LOT 2 RDG NUTELLA 1 - Le 2 ème à -50% en remise immédiate "
        "<br><i>pour un retrait jusqu'au 29/11</i>"
    )
    assert nettoyer_promo(brut) == (
        "Le 2 ème à -50% en remise immédiate · pour un retrait jusqu'au 29/11"
    )
    assert nettoyer_promo("-20% immédiat") == "-20% immédiat"
    assert nettoyer_promo("") == ""


def test_meme_produit_retrouve_par_nom_et_format(reglages):
    db.initialiser(reglages.db_path)
    with db.connexion(reglages.db_path) as cnx:
        for nom, ean in (("le pot de 400g", "3017620422003"), ("le pot de 825g", "3017620425035")):
            releve = ProduitObserve(
                produit=f"Pâte à tartiner aux noisettes et au cacao Nutella {nom}",
                prix_eur=Decimal("3.49"),
                ean=ean,
                url=f"https://www.intermarche.com/produit/nutella/{ean}",
            )
            observer(cnx, "intermarche-05052", releve, datetime.now(UTC).isoformat(), "Edge")
    ligne = LigneListe(
        id=1,
        mode=ModeLigne.PRODUIT,
        ean="8000500310427",  # un autre code-barres du Nutella 400 g
        recherche="nutella",
        libelle="Nutella · Ferrero 400 g",
    )
    trouve = _meme_produit_par_nom(reglages, "intermarche-05052", ligne)
    assert trouve and trouve["ean"] == "3017620422003"
    assert "autre code-barres" in trouve["source"]

    # Sans format dans la ligne, on ne devine pas.
    assert (
        _meme_produit_par_nom(
            reglages, "intermarche-05052", ligne.model_copy(update={"libelle": "Nutella"})
        )
        is None
    )
