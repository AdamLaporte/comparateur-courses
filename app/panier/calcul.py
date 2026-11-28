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

from app.collecte.equivalence import quantite_comparable
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
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


def ecrire_reference(reference: tuple[float, str]) -> str:
    """(12, "piece") → « 12 unités », (1000, "ml") → « 1 L », (500, "g") → « 500 g »."""
    valeur, famille = reference
    nombre = f"{valeur:g}".replace(".", ",")
    if famille == "piece":
        return f"{nombre} unité{'s' if valeur > 1 else ''}"
    if valeur >= 1000:
        return f"{valeur / 1000:g}".replace(".", ",") + (" kg" if famille == "g" else " L")
    return f"{nombre} {famille}"


def completer(
    ligne: LigneListe,
    resultat: ResultatLigne,
    cartes: frozenset[Enseigne] = frozenset(),
    reference: tuple[float, str] | None = None,
) -> ResultatLigne:
    """Ajoute le sous-total et les économies à un résultat trouvé.

    `reference` (ligne « le moins cher ») : quantité commune à tous les magasins, ex. (12, "piece"). Si
    l'offre choisie a un autre format de même nature (boîte de 6), son prix est ramené à cette quantité
    (× 2) pour comparer les magasins à égalité ; la case l'indique (« prix ramené à 12 unités »)."""
    if resultat.prix is None:
        return resultat
    enseigne = resultat.magasin_id.split("-", 1)[0]
    total, economies = sous_total(ligne, resultat.prix, avec_carte=enseigne in cartes)
    remarque = resultat.remarque
    if reference is not None and ligne.mode == ModeLigne.EQUIVALENT:
        quantite = quantite_comparable(
            f"{resultat.prix.produit.quantite or ''} {resultat.prix.produit.libelle}"
        )
        if (
            quantite
            and quantite[1] == reference[1]
            and abs(quantite[0] - reference[0]) > 0.01 * reference[0]
        ):
            facteur = reference[0] / quantite[0]
            total, economies = round(total * facteur), round(economies * facteur)
            mention = f"prix ramené à {ecrire_reference(reference)}"
            remarque = f"{remarque} · {mention}" if remarque else mention
    return resultat.model_copy(
        update={"sous_total_centimes": total, "economies_centimes": economies, "remarque": remarque}
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


def economie_du_meilleur(totaux: list[TotalMagasin], resultats: Iterable[ResultatLigne]) -> int:
    """Centimes économisés dans le premier magasin du classement par rapport au plus cher de ceux qui ont
    trouvé exactement les mêmes articles (un total avec d'autres articles ne se compare pas). 0 sinon."""
    articles: dict[str, set[int]] = {}
    for r in resultats:
        if r.statut == StatutPrix.TROUVE and r.sous_total_centimes is not None:
            articles.setdefault(r.magasin_id, set()).add(r.ligne_id)
    if not totaux or not articles.get(totaux[0].magasin.id):
        return 0
    meilleur = totaux[0]
    comparables = [
        t.total_centimes
        for t in totaux
        if articles.get(t.magasin.id) == articles[meilleur.magasin.id]
    ]
    return max(comparables) - meilleur.total_centimes
