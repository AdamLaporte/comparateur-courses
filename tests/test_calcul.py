"""Calcul des sous-totaux et des totaux (fonctions pures)."""

from datetime import UTC, datetime

from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Position,
    Prix,
    Produit,
    Promotion,
    ResultatLigne,
    StatutPrix,
    TypePromo,
    TypeSource,
)
from app.panier import calcul


def _ligne(identifiant: int = 1, quantite: int = 1) -> LigneListe:
    return LigneListe(
        id=identifiant, mode=ModeLigne.EQUIVALENT, recherche="x", libelle="x", quantite=quantite
    )


def _prix(centimes: int, promotions=(), prix_barre: int | None = None) -> Prix:
    return Prix(
        magasin_id="carrefour-1",
        produit=Produit(libelle="x"),
        prix_centimes=centimes,
        prix_barre_centimes=prix_barre,
        promotions=list(promotions),
        source=TypeSource.FICTIVE,
        releve_le=datetime.now(UTC),
        est_fictif=True,
    )


def _magasin(identifiant: str) -> Magasin:
    enseigne, id_enseigne = identifiant.split("-")
    return Magasin(
        id=identifiant,
        enseigne=Enseigne(enseigne),
        id_enseigne=id_enseigne,
        nom=identifiant,
        position=Position(lat=48.0, lon=-1.7),
    )


LOT = Promotion(libelle="Le 2e à -50 %", type=TypePromo.LOT, remise_centimes=150, quantite_min=2)
FIDELITE = Promotion(libelle="-10 % carte", type=TypePromo.FIDELITE, remise_centimes=30)


def test_promotion_lot_selon_la_quantite():
    assert calcul.sous_total(_ligne(quantite=1), _prix(300, [LOT])) == (300, 0)
    assert calcul.sous_total(_ligne(quantite=2), _prix(300, [LOT])) == (450, 150)
    assert calcul.sous_total(_ligne(quantite=3), _prix(300, [LOT])) == (750, 150)


def test_fidelite_ignoree_sans_carte():
    assert calcul.sous_total(_ligne(quantite=2), _prix(300, [FIDELITE])) == (600, 0)
    assert calcul.sous_total(_ligne(quantite=2), _prix(300, [FIDELITE]), avec_carte=True) == (
        540,
        60,
    )


def test_promotion_immediate_deja_deduite():
    # 240 = prix en caisse, 300 = ancien prix : le total utilise 240, l'économie est affichée.
    assert calcul.sous_total(_ligne(quantite=2), _prix(240, prix_barre=300)) == (480, 120)


def test_totaux_manquants_et_classement():
    lignes = [_ligne(1), _ligne(2)]
    magasins = [_magasin("carrefour-1"), _magasin("leclerc-2"), _magasin("coursesu-3")]
    trouve = StatutPrix.TROUVE

    def res(ligne_id, magasin_id, statut, sous_total=None):
        return ResultatLigne(
            ligne_id=ligne_id, magasin_id=magasin_id, statut=statut, sous_total_centimes=sous_total
        )

    resultats = [
        res(1, "carrefour-1", trouve, 500),
        res(2, "carrefour-1", trouve, 400),
        res(1, "leclerc-2", trouve, 450),
        res(2, "leclerc-2", trouve, 400),
        res(1, "coursesu-3", trouve, 100),
        res(2, "coursesu-3", StatutPrix.INTROUVABLE),
    ]
    totaux = calcul.totaux(lignes, magasins, resultats)

    assert [t.magasin.id for t in totaux] == ["leclerc-2", "carrefour-1", "coursesu-3"]
    assert [t.rang for t in totaux] == [1, 2, 3]
    assert totaux[0].total_centimes == 850 and totaux[0].complet
    incomplet = totaux[2]
    assert incomplet.total_centimes == 100
    assert incomplet.nb_manquants == 1 and not incomplet.complet


def test_totaux_en_cours_de_collecte():
    lignes = [_ligne(1), _ligne(2)]
    magasins = [_magasin("carrefour-1")]
    resultats = [
        ResultatLigne(
            ligne_id=1, magasin_id="carrefour-1", statut=StatutPrix.TROUVE, sous_total_centimes=200
        )
    ]
    total = calcul.totaux(lignes, magasins, resultats)[0]
    assert total.nb_en_attente == 1
    assert not total.complet


def test_economie_entre_magasins_qui_ont_les_memes_articles():
    lignes = [_ligne(1), _ligne(2)]
    magasins = [_magasin(f"carrefour-{n}") for n in (1, 2, 3, 4)]

    def trouve(ligne: int, numero: int, centimes: int) -> ResultatLigne:
        return ResultatLigne(
            ligne_id=ligne,
            magasin_id=f"carrefour-{numero}",
            statut=StatutPrix.TROUVE,
            prix=_prix(centimes),
            sous_total_centimes=centimes,
        )

    # 1 et 2 : l'article 1 seul. 3 : l'article 2 seul, plus cher mais non comparable.
    resultats = [trouve(1, 1, 100), trouve(1, 2, 175), trouve(2, 3, 900)]
    for numero, ligne in ((1, 2), (2, 2), (3, 1), (4, 1), (4, 2)):
        resultats.append(
            ResultatLigne(
                ligne_id=ligne,
                magasin_id=f"carrefour-{numero}",
                statut=StatutPrix.INTROUVABLE,
            )
        )
    totaux = calcul.totaux(lignes, magasins, resultats)
    assert totaux[0].magasin.id == "carrefour-1"
    assert calcul.economie_du_meilleur(totaux, resultats) == 75
    assert calcul.economie_du_meilleur(totaux[:1], resultats) == 0
    assert calcul.economie_du_meilleur([], []) == 0
