import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app.config import Reglages, ReglagesDep
from app.drives.modeles import (
    DRIVES,
    Depot,
    DriveId,
    EnseigneDrive,
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

router = APIRouter(tags=["drives"])


@router.post("/api/drives/recherches")
def lancer_api(recherche: Recherche, reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return rechercher(reglages, recherche, creer=True)


@router.get("/api/drives/suivi")
def suivi_api(recherche: Annotated[Recherche, Query()], reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return rechercher(reglages, recherche, creer=False)


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
    signaler(reglages, drive)


@router.post("/api/drives/{drive}/prendre")
def prendre_api(
    request: Request,
    drive: DriveId,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    collecteur = _autoriser(request, reglages, x_drives_jeton)
    return prendre(reglages, drive, collecteur)


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
    return [
        point_collecteur(drive, point)
        for drive, point in DRIVES.items()
        if drive.startswith(enseigne + "-")
    ]


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
