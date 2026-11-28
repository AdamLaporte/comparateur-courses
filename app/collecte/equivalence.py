"""Mode « équivalent » (« le moins cher ») : choisir une offre parmi celles qui correspondent à la recherche.

Utilisé par l'orchestrateur (source de l'enseigne), par le repli (Open Prices) et par les drives, pour que
la règle soit la même partout :
1. le produit doit avoir la recherche pour **sujet** : le premier mot important de son nom (sans la marque
   ni « gros », « bio », « boîte de »…) commence comme le premier mot cherché. « lait » garde « Lait
   demi-écrémé » mais écarte « Gâteau au chocolat au lait » ; « oeufs » écarte « Pâtes aux œufs ».
   Si aucune offre n'a ce sujet, on garde toutes les offres (jamais de résultat vide à cause du filtre) ;
2. parmi elles, la moins chère **à l'unité** (au gramme, au millilitre ou à la pièce), calculée à partir du
   format (« 500 g », « 1 L », « boîte de 12 », « x6 ») ; sans format connu, au prix affiché.
`quantite_comparable` sert aussi à ramener les prix à une même quantité (app/panier/calcul.py).
"""

import re
from collections import Counter

from app.contrats import Prix
from app.produits.service import lire_quantite, normaliser

# Nombre de pièces : « x12 », « 12 x », « 6 gros œufs », « 24 rouleaux », « boîte de 6 », « lot de 4 ».
_UNITES_PIECES = (
    r"oeufs?|pieces?|pcs?|rouleaux?|unites?|sachets?|capsules?|dosettes?|portions?|pots?|"
    r"bouteilles?|canettes?|briques?|tranches?|barres?|biscuits?|yaourts?|paquets?"
)
_MOTIF_PIECES = re.compile(
    r"(?:\bx\s*(\d+)\b"
    r"|\b(\d+)\s*x\b"
    rf"|\b(\d+)\s+(?:[a-z]+\s+){{0,2}}(?:{_UNITES_PIECES})\b"
    rf"|\b(\d+)\s*(?:{_UNITES_PIECES})\b"
    r"|\b(?:boite|lot|pack|plaque|etui|barquette|coffret)\s+(?:de\s+)?(\d+)\b)"
)

# Mots qui ne sont jamais le sujet d'un produit.
_PAS_SUJET = {
    "le", "la", "les", "l", "de", "du", "des", "d", "un", "une", "au", "aux", "a", "et", "en", "avec",
    "gros", "grosse", "grosses", "petit", "petits", "petite", "petites", "mini", "maxi", "extra", "super",
    "bio", "frais", "fraiche", "fraiches", "nouveau", "nouvelle", "plein", "air", "label", "rouge",
    "boite", "pack", "lot", "sachet", "barquette", "bouteille", "brique", "pot", "x", "etui", "format",
    "familial", "original", "classique", "tradition", "marque", "repere",
}  # fmt: skip


def quantite_comparable(texte: str | None) -> tuple[float, str] | None:
    """Quantité totale pour comparer des prix : (grammes, "g"), (millilitres, "ml") ou (pièces, "piece").
    « 500 g » → (500, "g") ; « 6 x 1 L » → (6000, "ml") ; « Boîte de 12 » ou « x12 » → (12, "piece")."""
    if quantite := lire_quantite(texte):
        return quantite
    trouve = _MOTIF_PIECES.search(normaliser(texte))
    if trouve is None:
        return None
    nombre = int(next(g for g in trouve.groups() if g))
    return (float(nombre), "piece") if 1 <= nombre <= 500 else None


def _quantite_offre(offre: Prix) -> tuple[float, str] | None:
    return quantite_comparable(f"{offre.produit.quantite or ''} {offre.produit.libelle}")


def _singulier(mot: str) -> str:
    return mot[:-1] if len(mot) > 3 and mot[-1] in "sx" else mot


def a_pour_sujet(offre: Prix, recherche: str) -> bool:
    return est_le_sujet(offre.produit.libelle, offre.produit.marque, recherche)


def est_le_sujet(libelle: str, marque: str | None, recherche: str) -> bool:
    """Le premier mot important du nom (sans la marque) commence comme le premier mot cherché."""
    cherches = [m for m in normaliser(recherche).split() if m not in _PAS_SUJET and not m.isdigit()]
    if not cherches:
        return True
    mots_marque = set(normaliser(marque).split())
    mots = [
        m
        for m in normaliser(libelle).split()
        if m not in _PAS_SUJET and m not in mots_marque and not any(c.isdigit() for c in m)
    ]
    return bool(mots) and _singulier(mots[0]).startswith(_singulier(cherches[0]))


def choisir_equivalent(offres: list[Prix], recherche: str | None = None) -> Prix | None:
    """L'offre qui a la recherche pour sujet, la moins chère à l'unité (voir l'en-tête du module)."""
    if not offres:
        return None
    if recherche:
        offres = [o for o in offres if a_pour_sujet(o, recherche)] or offres
    mesurees = [(o, q) for o in offres if (q := _quantite_offre(o)) is not None]
    if mesurees:
        famille = Counter(q[1] for _, q in mesurees).most_common(1)[0][0]
        return min(
            ((o, q) for o, q in mesurees if q[1] == famille),
            key=lambda e: (e[0].prix_centimes / e[1][0], e[0].prix_centimes),
        )[0]
    if all(o.prix_unitaire_centimes is not None for o in offres):
        return min(offres, key=lambda o: (o.prix_unitaire_centimes, o.prix_centimes))
    return min(offres, key=lambda o: o.prix_centimes)
