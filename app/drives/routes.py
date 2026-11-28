import asyncio
import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app import db
from app.config import Reglages, ReglagesDep
from app.drives.catalogue import PointInconnu, inscrire, points_inscrits
from app.drives.modeles import (
    DRIVES,
    Depot,
    DriveId,
    EnseigneDrive,
    InscriptionRetrait,
    PointRetrait,
    Recherche,
    point_collecteur,
)
from app.drives.service import (
    BailInvalide,
    deposer,
    prendre,
    prendre_enseigne,
    rechercher,
    signaler,
    signaler_enseigne,
)
from app.magasins.geocodage import CodePostalInconnu, geocoder_retrait

router = APIRouter(tags=["drives"])


@router.post("/api/drives/recherches")
def lancer_api(recherche: Recherche, reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return rechercher(reglages, recherche, creer=True)
    except PointInconnu as exc:
        raise HTTPException(422, "Point de retrait non répertorié.") from exc


@router.get("/api/drives/suivi")
def suivi_api(recherche: Annotated[Recherche, Query()], reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return rechercher(reglages, recherche, creer=False)
    except PointInconnu as exc:
        raise HTTPException(422, "Point de retrait non répertorié.") from exc


def _autoriser(request: Request, reglages: Reglages, jeton: str) -> str | None:
    if reglages.site_partage_origine:
        for identifiant, secret in reglages.drives_collecteurs.items():
            if secrets.compare_digest(jeton.encode(), secret.get_secret_value().encode()):
                return identifiant
        raise HTTPException(401, "Jeton de collecte invalide.")
    if request.client is None or request.client.host != "127.0.0.1":
        raise HTTPException(403, "Collecte réservée à la connexion locale.")
    if not reglages.drives_jeton or not secrets.compare_digest(
        jeton.encode("utf-8"), reglages.drives_jeton.encode("utf-8")
    ):
        raise HTTPException(401, "Jeton de collecte invalide.")


@router.post("/api/drives/{drive}/connexion", status_code=204)
def connecter(
    request: Request,
    drive: DriveId,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    try:
        signaler(reglages, drive)
    except PointInconnu as exc:
        raise HTTPException(422, "Point de retrait non répertorié.") from exc


@router.post("/api/drives/{drive}/prendre")
def prendre_api(
    request: Request,
    drive: DriveId,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    collecteur = _autoriser(request, reglages, x_drives_jeton)
    try:
        return prendre(reglages, drive, collecteur)
    except PointInconnu as exc:
        raise HTTPException(422, "Point de retrait non répertorié.") from exc


@router.post("/api/drives/enseignes/{enseigne}/connexion", status_code=204)
def connecter_enseigne(
    request: Request,
    enseigne: EnseigneDrive,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    signaler_enseigne(reglages, enseigne)


@router.post("/api/drives/enseignes/{enseigne}/prendre")
def prendre_api_enseigne(
    request: Request,
    enseigne: EnseigneDrive,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    collecteur = _autoriser(request, reglages, x_drives_jeton)
    return prendre_enseigne(reglages, enseigne, collecteur)


@router.post("/api/drives/enseignes/{enseigne}/points-retrait")
def points_retrait_api(
    request: Request,
    enseigne: EnseigneDrive,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    with db.connexion(reglages.db_path) as cnx:
        points = {**DRIVES, **points_inscrits(cnx)}
    return [
        point_collecteur(drive, point)
        for drive, point in points.items()
        if drive.startswith(enseigne + "-")
    ]


@router.post("/api/drives/enseignes/{enseigne}/inscrire-point-retrait")
async def inscrire_point_retrait(
    request: Request,
    enseigne: EnseigneDrive,
    inscription: InscriptionRetrait,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    try:
        drive = inscription.identifiant(enseigne)
        accueil = inscription.accueil_canonique(enseigne)
    except ValueError as exc:
        raise HTTPException(
            422, "Le lien du magasin ne correspond pas au retrait détecté."
        ) from exc
    for identifiant, initial in DRIVES.items():
        if identifiant != drive and identifiant.startswith(enseigne + "-"):
            point = point_collecteur(identifiant, initial)
            if point["reference"] == inscription.reference:
                return point
    try:
        ville, position = await geocoder_retrait(
            inscription.adresse, inscription.code_postal, reglages
        )
    except CodePostalInconnu as exc:
        raise HTTPException(422, "Adresse du point de retrait introuvable.") from exc
    point = PointRetrait(
        nom=inscription.libelle,
        adresse=inscription.adresse,
        code_postal=inscription.code_postal,
        ville=ville,
        accueil=accueil,
        libelles=[inscription.libelle],
        coordonnees=(position.lat, position.lon),
        reference=inscription.reference,
    )
    await asyncio.to_thread(inscrire, reglages.db_path, drive, point)
    return point_collecteur(drive, point)


@router.post("/api/drives/taches/{tache_id}/depot", status_code=204)
def deposer_api(
    request: Request,
    tache_id: int,
    depot: Depot,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    collecteur = _autoriser(request, reglages, x_drives_jeton)
    try:
        deposer(reglages, tache_id, depot, collecteur)
    except BailInvalide as exc:
        raise HTTPException(409, "Bail ou drive invalide.") from exc
    except ValueError as exc:
        raise HTTPException(422, "Observation marchande invalide.") from exc
