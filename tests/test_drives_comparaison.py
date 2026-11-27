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


def test_texte_envoye_au_drive_sans_quantites_ni_symboles():
    from app.drives.modeles import terme_simplifie

    assert terme_simplifie("carré frais 200gr*8 0%") == "carré frais"
    assert terme_simplifie("lait demi-écrémé 1 l") == "lait demi-écrémé"
    assert terme_simplifie("pâtes spaghetti n°5 500g") == "pâtes spaghetti"
    assert terme_simplifie("yaourt nature 4x125g") == "yaourt nature"
    assert terme_simplifie("3017620422003") == "3017620422003"  # un EAN reste un EAN


def test_la_tache_de_l_extension_porte_le_texte_simplifie(reglages):
    from app.drives.modeles import Recherche
    from app.drives.service import rechercher_pour_panier

    reglages.drives_jeton = "j" * 32
    db.initialiser(reglages.db_path)
    recherche = Recherche(q="carré frais 200gr*8 0%", drives=["intermarche-05052"])
    rechercher_pour_panier(
        reglages, "intermarche-05052", recherche, creer=True, terme_marchand=None
    )
    with db.connexion(reglages.db_path) as cnx:
        assert cnx.execute("SELECT requete FROM drive_tache").fetchone()[0] == "carré frais"


def test_le_moins_cher_parmi_les_resultats_concordants():
    from app.drives.comparaison import _choisir_concordant, _prix

    def produit(nom, centimes, format_=""):
        return {
            "produit": nom, "marque": "", "format": format_, "ean": "", "prix_centimes": centimes,
            "prix_par_unite_eur": None, "unite": "", "source": "Edge", "ancien": False,
            "releve_le": "2026-11-28T10:00:00+00:00", "promos": "",
        }  # fmt: skip

    produits = [
        produit("Fromage frais nature", 99),
        produit("Carré frais 0% 200g", 250, "200g"),
        produit("Carré frais 0% 100g", 160, "100g"),
    ]
    offres = [_prix("intermarche-05052", p) for p in produits]
    ligne = LigneListe(
        id=1, mode=ModeLigne.EQUIVALENT, recherche="carré frais 200gr*8 0%", libelle="carré frais"
    )
    # Pas le fromage à 0,99 € (autre produit), et le bon format (200 g) avant le moins cher.
    assert _choisir_concordant(ligne, produits, offres).prix_centimes == 250
    sans_format = ligne.model_copy(update={"recherche": "carré frais"})
    assert _choisir_concordant(sans_format, produits, offres).prix_centimes == 160
    inconnu = ligne.model_copy(update={"recherche": "xyz"})
    assert _choisir_concordant(inconnu, produits, offres).prix_centimes == 99  # le premier résultat
