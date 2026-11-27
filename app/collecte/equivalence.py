"""Mode « équivalent » : choisir une offre parmi celles qui correspondent à la recherche.

Utilisé par l'orchestrateur (source de l'enseigne) et par le repli (Open Prices), pour que la règle
soit la même partout. Point d'accroche du mode « fin de mois » (lot 4, bonus).
"""

from app.contrats import Prix


def choisir_equivalent(offres: list[Prix]) -> Prix | None:
    """L'offre la moins chère, au prix unitaire si toutes l'ont, sinon au prix."""
    if not offres:
        return None
    if all(o.prix_unitaire_centimes is not None for o in offres):
        return min(offres, key=lambda o: (o.prix_unitaire_centimes, o.prix_centimes))
    return min(offres, key=lambda o: o.prix_centimes)
