"""Points de retrait pris en charge (app/drives/points_retrait.json) vus comme des magasins."""

from app.contrats import Enseigne, Magasin, Position
from app.drives.modeles import PointRetrait


def magasin_retrait(drive: str, point: PointRetrait, coordonnees: tuple[float, float]) -> Magasin:
    enseigne, identifiant = drive.split("-", 1)
    lat, lon = coordonnees
    return Magasin(
        id=drive,
        enseigne=Enseigne(enseigne),
        id_enseigne=identifiant,
        nom=point.nom,
        adresse=f"{point.adresse}, {point.code_postal} {point.ville}",
        code_postal=point.code_postal,
        ville=point.ville,
        position=Position(lat=lat, lon=lon),
    )
