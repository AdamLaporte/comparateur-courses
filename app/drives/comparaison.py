"""Pont entre la comparaison de « Ma liste » et les drives de Bruz relevés par les extensions Edge.

Quand un article n'a pas de prix dans un magasin qui correspond à un drive (Super U Bruz, Intermarché
Bruz Cap Vert) — introuvable, indisponible, ou « inexistant » dans notre catalogue — on regarde les
relevés des extensions ; s'il n'y en a pas de récent, on crée une recherche que l'extension du drive
fera d'elle-même dans l'onglet ouvert (elle passe toutes les 30 s). Il faut DRIVES_JETON réglé.
"""

import math
from datetime import UTC, datetime

from app.config import Reglages
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Position,
    Prix,
    Produit,
    TypeSource,
)
from app.drives.modeles import DRIVES, Recherche, ean_valide
from app.drives.service import rechercher

DRIVE_PAR_ENSEIGNE = {
    Enseigne.COURSES_U: "coursesu-33315",
    Enseigne.INTERMARCHE: "intermarche-05052",
}
# shortcut: les deux drives sont à Bruz ; on prend le magasin de même enseigne le plus proche du centre,
# à moins de 3 km. À remplacer par les coordonnées exactes des drives s'il y en a d'autres.
CENTRE_BRUZ = Position(lat=48.02516, lon=-1.748362)
RAYON_KM = 3.0
EN_ATTENTE = ("attente", "cours")


def _distance_km(a: Position, b: Position) -> float:
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    h = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(b.lon - a.lon) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def associer(magasins: list[Magasin]) -> dict[str, str]:
    """magasin_id → drive_id, pour les magasins du tableau qui sont l'un des deux drives de Bruz."""
    associations = {}
    for enseigne, drive in DRIVE_PAR_ENSEIGNE.items():
        candidats = [
            (_distance_km(CENTRE_BRUZ, m.position), m.id)
            for m in magasins
            if m.enseigne == enseigne
        ]
        candidats = [c for c in candidats if c[0] <= RAYON_KM]
        if candidats:
            associations[min(candidats)[1]] = drive
    return associations


def _texte(ligne: LigneListe) -> str:
    if ligne.mode == ModeLigne.PRODUIT and ligne.ean and ean_valide(ligne.ean):
        return ligne.ean
    return ligne.recherche[:160]


def _prix(produit: dict, magasin: Magasin, drive: str) -> Prix:
    try:
        releve = datetime.fromisoformat(produit.get("releve_le", "")).astimezone(UTC)
    except ValueError:
        releve = datetime.now(UTC)
    unitaire = produit.get("prix_par_unite_eur")
    return Prix(
        magasin_id=magasin.id,
        produit=Produit(
            ean=produit.get("ean") or None,
            libelle=produit.get("produit") or "?",
            marque=produit.get("marque") or None,
            quantite=produit.get("format") or None,
        ),
        prix_centimes=int(produit["prix_centimes"]),
        prix_unitaire_centimes=round(float(unitaire) * 100) if unitaire else None,
        unite=produit.get("unite") or None,
        source=TypeSource.COLLECTE,
        source_detail=f"Drive {DRIVES[drive][0]} (extension)",
        releve_le=releve,
    )


def chercher(
    reglages: Reglages, ligne: LigneListe, magasin: Magasin, drive: str, *, creer: bool
) -> tuple[str, Prix | None]:
    """(état, prix) : « recent » avec un prix, « attente »/« cours » pendant que l'extension cherche,
    sinon un état sans prix (« vide », « echec », « pause », « indisponible »…)."""
    vue = rechercher(reglages, Recherche(q=_texte(ligne), drives=[drive]), creer=creer)[0]
    produits = [p for p in vue["produits"] if not p.get("ancien")] or vue["produits"]
    if vue["etat"] in EN_ATTENTE and not [p for p in produits if not p.get("ancien")]:
        return vue["etat"], None
    if not produits:
        return vue["etat"], None
    if ligne.mode == ModeLigne.PRODUIT and ligne.ean:
        exacts = [p for p in produits if p.get("ean") == ligne.ean]
        choisi = exacts[0] if exacts else produits[0]
    else:
        # « Le moins cher » : le moins cher des produits les plus pertinents.
        choisi = min(produits[:5], key=lambda p: p["prix_centimes"])
    return "recent", _prix(choisi, magasin, drive)
