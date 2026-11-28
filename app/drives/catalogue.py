"""Catalogue initial et points de retrait enregistrés depuis les extensions Edge."""

import sqlite3
from pathlib import Path

from app import db
from app.contrats import Enseigne, Magasin, Position
from app.drives.modeles import DRIVES, PointRetrait


class PointInconnu(LookupError):
    """Le point de retrait n'a pas été enregistré."""


def point_retrait(cnx: sqlite3.Connection, drive: str) -> PointRetrait:
    ligne = cnx.execute(
        "SELECT donnees FROM drive_point_retrait WHERE drive_id=?", (drive,)
    ).fetchone()
    if ligne is not None:
        return PointRetrait.model_validate_json(ligne["donnees"])
    if drive in DRIVES:
        return DRIVES[drive]
    raise PointInconnu(drive)


def points_inscrits(cnx: sqlite3.Connection) -> dict[str, PointRetrait]:
    return {
        ligne["drive_id"]: PointRetrait.model_validate_json(ligne["donnees"])
        for ligne in cnx.execute(
            "SELECT drive_id, donnees FROM drive_point_retrait ORDER BY drive_id"
        )
    }


def inscrire(chemin_db: Path, drive: str, point: PointRetrait) -> None:
    with db.connexion(chemin_db) as cnx:
        cnx.execute(
            "INSERT INTO drive_point_retrait (drive_id, donnees) VALUES (?, ?) "
            "ON CONFLICT(drive_id) DO UPDATE SET donnees=excluded.donnees",
            (drive, point.model_dump_json()),
        )


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


def magasins_inscrits(chemin_db: Path) -> list[Magasin]:
    with db.connexion(chemin_db) as cnx:
        points = points_inscrits(cnx)
    return [
        magasin_retrait(drive, point, point.coordonnees)
        for drive, point in points.items()
        if point.coordonnees is not None
    ]
