"""Calcul des sous-totaux et des totaux par magasin. Fonctions pures, sans réseau ni base.

Règles (docs/architecture.md §9) :
- Prix.prix_centimes est le prix en caisse sans condition : la promotion immédiate y est déjà déduite
  (elle ne compte que dans les économies affichées) ;
- promotion « lot » : remise appliquée une fois par groupe de quantite_min articles ;
- promotion « fidélité » : déduite seulement si l'utilisateur a déclaré la carte de l'enseigne
  (fonctionnalité « long terme » : `cartes` vide par défaut) ;
- total d'un magasin = somme des lignes trouvées ; les manquants sont comptés à part ;
- classement : paniers complets du moins cher au plus cher, puis les incomplets.
"""

from collections.abc import Iterable

from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    Prix,
    ResultatLigne,
    StatutPrix,
    TotalMagasin,
    TypePromo,
)


def sous_total(ligne: LigneListe, prix: Prix, avec_carte: bool = False) -> tuple[int, int]:
    """(sous-total, économies) d'une ligne, en centimes."""
    brut = ligne.quantite * prix.prix_centimes
    remise = 0
    for promo in prix.promotions:
        declenchements = ligne.quantite // promo.quantite_min
        if promo.type == TypePromo.LOT or (promo.type == TypePromo.FIDELITE and avec_carte):
            remise += declenchements * promo.remise_centimes
    economies = remise
    if prix.prix_barre_centimes is not None and prix.prix_barre_centimes > prix.prix_centimes:
        economies += ligne.quantite * (prix.prix_barre_centimes - prix.prix_centimes)
    return max(0, brut - remise), economies


def completer(
    ligne: LigneListe, resultat: ResultatLigne, cartes: frozenset[Enseigne] = frozenset()
) -> ResultatLigne:
    """Ajoute le sous-total et les économies à un résultat trouvé."""
    if resultat.statut != StatutPrix.TROUVE or resultat.prix is None:
        return resultat
    enseigne = resultat.magasin_id.split("-", 1)[0]
    total, economies = sous_total(ligne, resultat.prix, avec_carte=enseigne in cartes)
    return resultat.model_copy(
        update={"sous_total_centimes": total, "economies_centimes": economies}
    )


def totaux(
    lignes: list[LigneListe], magasins: list[Magasin], resultats: Iterable[ResultatLigne]
) -> list[TotalMagasin]:
    """Total par magasin, trié par rang (1 = le moins cher). Les résultats doivent être complétés."""
    par_cle = {(r.ligne_id, r.magasin_id): r for r in resultats}
    liste = []
    for magasin in magasins:
        total = economies = trouves = manquants = en_attente = 0
        for ligne in lignes:
            resultat = par_cle.get((ligne.id, magasin.id))
            if resultat is None or resultat.statut == StatutPrix.EN_ATTENTE:
                en_attente += 1
            elif resultat.statut == StatutPrix.TROUVE and resultat.sous_total_centimes is not None:
                trouves += 1
                total += resultat.sous_total_centimes
                economies += resultat.economies_centimes
            else:
                manquants += 1
        liste.append(
            TotalMagasin(
                magasin=magasin,
                total_centimes=total,
                economies_centimes=economies,
                nb_trouves=trouves,
                nb_manquants=manquants,
                nb_en_attente=en_attente,
                complet=(manquants == 0 and en_attente == 0),
            )
        )
    liste.sort(key=lambda t: (not t.complet, t.nb_manquants + t.nb_en_attente, t.total_centimes))
    return [t.model_copy(update={"rang": rang}) for rang, t in enumerate(liste, start=1)]
