"""« Le moins cher » : sujet du produit, prix à l'unité et prix ramenés à une même quantité."""

from datetime import UTC, datetime

import pytest

from app.collecte.equivalence import a_pour_sujet, choisir_equivalent, quantite_comparable
from app.contrats import LigneListe, ModeLigne, Prix, Produit, ResultatLigne, StatutPrix, TypeSource
from app.panier.calcul import completer, ecrire_reference


def offre(libelle: str, centimes: int, quantite: str | None = None, marque: str | None = None):
    return Prix(
        magasin_id="intermarche-05052",
        produit=Produit(libelle=libelle, quantite=quantite, marque=marque),
        prix_centimes=centimes,
        source=TypeSource.COLLECTE,
        releve_le=datetime(2026, 11, 28, 9, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Boîte de 12", (12, "piece")),
        ("x6", (6, "piece")),
        ("Oeufs frais bio x12", (12, "piece")),
        ("6 Gros Œufs", (6, "piece")),
        ("12 pcs", (12, "piece")),
        ("24 rouleaux", (24, "piece")),
        ("500 g", (500, "g")),
        ("6 x 1 L", (6000, "ml")),
        ("Nutella", None),
    ],
)
def test_quantite_comparable(texte, attendu):
    assert quantite_comparable(texte) == attendu


def test_lait_n_est_pas_un_gateau_au_lait():
    gateau = offre("Gâteau au chocolat au lait", 150, "300 g")
    lait = offre("Lait demi-écrémé", 105, "1 L", "Lactel")
    lait_marque_devant = offre("Lactel lait demi-écrémé bio", 130, "1 L", "Lactel")
    assert not a_pour_sujet(gateau, "lait")
    assert a_pour_sujet(lait, "lait") and a_pour_sujet(lait_marque_devant, "lait")
    assert choisir_equivalent([gateau, lait, lait_marque_devant], "lait") is lait


def test_oeufs_moins_chers_a_l_unite_et_pas_les_pates_aux_oeufs():
    boite_6 = offre("Oeufs frais", 180, "6 pcs")  # 0,30 € l'œuf
    boite_12 = offre("Gros oeufs plein air", 300, "Boîte de 12")  # 0,25 € l'œuf
    pates = offre("Pâtes aux oeufs", 90, "500 g")
    assert choisir_equivalent([boite_6, boite_12, pates], "oeufs") is boite_12


def test_sans_produit_au_bon_sujet_on_garde_toutes_les_offres():
    seul = offre("Fromage frais nature", 99)
    assert choisir_equivalent([seul], "carré frais") is seul


def test_prix_ramene_a_la_quantite_de_reference():
    ligne = LigneListe(id=1, mode=ModeLigne.EQUIVALENT, recherche="oeufs", libelle="oeufs")
    boite_6 = ResultatLigne(
        ligne_id=1, magasin_id="coursesu-33315", statut=StatutPrix.TROUVE,
        prix=offre("Oeufs frais", 180, "6 pcs"),
    )  # fmt: skip
    ramene = completer(ligne, boite_6, reference=(12, "piece"))
    assert ramene.sous_total_centimes == 360  # 2 boîtes de 6 pour comparer à une boîte de 12
    assert ramene.remarque == "prix ramené à 12 unités"

    # Même format, autre nature ou ligne « produit précis » : prix inchangé.
    assert completer(ligne, boite_6, reference=(6, "piece")).sous_total_centimes == 180
    assert completer(ligne, boite_6, reference=(1000, "g")).sous_total_centimes == 180
    precis = ligne.model_copy(update={"mode": ModeLigne.PRODUIT, "ean": "3270190025795"})
    assert completer(precis, boite_6, reference=(12, "piece")).sous_total_centimes == 180


def test_ecrire_reference():
    assert ecrire_reference((12, "piece")) == "12 unités"
    assert ecrire_reference((1000, "ml")) == "1 L"
    assert ecrire_reference((1500, "g")) == "1,5 kg"
    assert ecrire_reference((500, "g")) == "500 g"
