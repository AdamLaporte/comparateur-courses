"""Lieux enregistrés par compte."""

from app.config import Reglages
from app.contrats import Position
from app.db import connexion
from app.magasins.geocodage import CodePostalInvalide, geocoder
from app.magasins.trajets import MODES


def lister(reglages: Reglages, utilisateur_id: int | None) -> list[dict]:
    if utilisateur_id is None:
        return []
    with connexion(reglages.db_path) as cnx:
        return [
            dict(lieu)
            for lieu in cnx.execute(
                """SELECT id, nom, adresse, lat, lon, mode FROM lieu_trajet
                   WHERE utilisateur_id = ? ORDER BY nom COLLATE NOCASE, id""",
                (utilisateur_id,),
            )
        ]


async def enregistrer(
    reglages: Reglages, utilisateur_id: int, nom: str, adresse: str, mode: str, lieu_id: int | None
) -> None:
    nom, adresse = nom.strip(), adresse.strip()
    if not 1 <= len(nom) <= 60 or not 1 <= len(adresse) <= 160 or mode not in MODES:
        raise CodePostalInvalide(adresse)
    if lieu_id is not None:
        existant = next(
            (lieu for lieu in lister(reglages, utilisateur_id) if lieu["id"] == lieu_id), None
        )
        if existant is None:
            raise LookupError(lieu_id)
    else:
        existant = None
    if existant and existant["adresse"] == adresse:
        position = Position(lat=existant["lat"], lon=existant["lon"])
    else:
        _, position = await geocoder(adresse, reglages, adresse=True)
    with connexion(reglages.db_path) as cnx:
        donnees = (nom, adresse, position.lat, position.lon, mode, utilisateur_id)
        if lieu_id is None:
            cnx.execute(
                """INSERT INTO lieu_trajet (nom, adresse, lat, lon, mode, utilisateur_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                donnees,
            )
        else:
            cnx.execute(
                """UPDATE lieu_trajet SET nom = ?, adresse = ?, lat = ?, lon = ?, mode = ?
                   WHERE utilisateur_id = ? AND id = ?""",
                (*donnees, lieu_id),
            )


def supprimer(reglages: Reglages, utilisateur_id: int, lieu_id: int) -> None:
    with connexion(reglages.db_path) as cnx:
        cnx.execute(
            "DELETE FROM lieu_trajet WHERE utilisateur_id = ? AND id = ?", (utilisateur_id, lieu_id)
        )
