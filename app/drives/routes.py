import secrets
from datetime import date, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from app.config import Reglages, ReglagesDep
from app.drives.modeles import DRIVES, Depot, DriveId, Recherche
from app.drives.service import BailInvalide, deposer, prendre, rechercher
from app.gabarits import PARIS, templates

router = APIRouter(tags=["drives"])
MESSAGES = {
    "mauvais_drive": "Le point de retrait actif ne correspond pas au drive demandé.",
    "page_inattendue": "La page marchande n’a pas permis de confirmer le résultat.",
    "reseau": "Erreur de connexion au site marchand.",
    "delai": "Le relevé a expiré. Relancez la recherche pour réessayer.",
    "403": "Le site marchand a refusé l’accès.",
    "429": "Le site marchand a limité les requêtes.",
    "defi": "Le site marchand demande une vérification.",
    "404": "La page de recherche est introuvable.",
}


def _date_affichee(texte: str) -> str:
    if len(texte) == 10:
        return date.fromisoformat(texte).strftime("%d/%m/%Y")
    return datetime.fromisoformat(texte).astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


def _rendre(request: Request, recherche=None, resultats=(), erreur=""):
    for resultat in resultats:
        for produit in resultat["produits"]:
            produit["date_affichee"] = _date_affichee(produit["releve_le"])
    fragment = request.headers.get("HX-Request") == "true"
    return templates.TemplateResponse(
        request,
        "drives/_resultats.html" if fragment else "drives/page.html",
        {
            "drives": DRIVES,
            "recherche": recherche,
            "resultats": resultats,
            "erreur_formulaire": erreur,
            "messages": MESSAGES,
            "suivi": urlencode({"q": recherche.q, "drives": recherche.drives}, doseq=True)
            if recherche
            else "",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/drives", response_class=HTMLResponse)
def page_drives(request: Request):
    return _rendre(request)


@router.post("/drives", response_class=HTMLResponse)
def lancer(
    request: Request,
    reglages: ReglagesDep,
    q: Annotated[str, Form()] = "",
    drives: Annotated[list[str] | None, Form()] = None,
):
    try:
        recherche = Recherche.model_validate({"q": q, "drives": drives or []})
    except ValidationError:
        return _rendre(request, erreur="Saisissez un produit et choisissez un drive.")
    return _rendre(request, recherche, rechercher(reglages, recherche, creer=True))


@router.get("/drives/suivi", response_class=HTMLResponse)
def suivi(request: Request, reglages: ReglagesDep, recherche: Annotated[Recherche, Query()]):
    return _rendre(request, recherche, rechercher(reglages, recherche, creer=False))


@router.post("/api/drives/recherches")
def lancer_api(recherche: Recherche, reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return rechercher(reglages, recherche, creer=True)


@router.get("/api/drives/suivi")
def suivi_api(recherche: Annotated[Recherche, Query()], reglages: ReglagesDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return rechercher(reglages, recherche, creer=False)


def _autoriser(request: Request, reglages: Reglages, jeton: str) -> None:
    if request.client is None or request.client.host != "127.0.0.1":
        raise HTTPException(403, "Collecte réservée à la connexion locale.")
    if not reglages.drives_jeton or not secrets.compare_digest(
        jeton.encode("utf-8"), reglages.drives_jeton.encode("utf-8")
    ):
        raise HTTPException(401, "Jeton de collecte invalide.")


@router.post("/api/drives/{drive}/prendre")
def prendre_api(
    request: Request,
    drive: DriveId,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    return prendre(reglages, drive)


@router.post("/api/drives/taches/{tache_id}/depot", status_code=204)
def deposer_api(
    request: Request,
    tache_id: int,
    depot: Depot,
    reglages: ReglagesDep,
    x_drives_jeton: Annotated[str, Header()] = "",
):
    _autoriser(request, reglages, x_drives_jeton)
    try:
        deposer(reglages, tache_id, depot)
    except BailInvalide as exc:
        raise HTTPException(409, "Bail ou drive invalide.") from exc
    except ValueError as exc:
        raise HTTPException(422, "Observation marchande invalide.") from exc
