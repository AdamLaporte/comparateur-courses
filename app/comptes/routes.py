"""Routes des comptes (facultatifs : tout le site marche sans compte).

/comptes                      page du compte (ou invitation à se connecter)
/comptes/inscription          créer un compte
/comptes/connexion            se connecter (rattache la liste faite sans compte)
/comptes/deconnexion          se déconnecter (POST)
/comptes/mot-de-passe         changer son mot de passe (connecté)
/comptes/mot-de-passe-perdu   recevoir un lien de réinitialisation
/comptes/reinitialiser        choisir un nouveau mot de passe depuis le lien
"""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.comptes import service
from app.comptes.service import ErreurCompte
from app.config import ReglagesDep
from app.gabarits import templates

router = APIRouter(prefix="/comptes", tags=["comptes"])

Champ = Annotated[str, Form()]


def _page(request: Request, nom: str, statut: int = 200, **contexte) -> HTMLResponse:
    return templates.TemplateResponse(request, f"comptes/{nom}.html", contexte, status_code=statut)


def _vers(chemin: str) -> RedirectResponse:
    return RedirectResponse(chemin, status_code=303)


def _suivant_sur(suivant: str) -> str:
    """Page où revenir après connexion : seulement un chemin de ce site (pas de redirection ouverte)."""
    if suivant.startswith("/") and not suivant.startswith("//") and "\\" not in suivant:
        return suivant
    return "/comptes"


def _ouvrir_session(request: Request, reglages, utilisateur_id: int, email: str) -> None:
    service.rattacher_liste(reglages, request.session.get("sid"), utilisateur_id)
    request.session.pop("sid", None)
    request.session["utilisateur_id"] = utilisateur_id
    request.session["email"] = email


@router.get("", response_class=HTMLResponse)
async def page_compte(request: Request, reglages: ReglagesDep):
    utilisateur_id = request.session.get("utilisateur_id")
    email = service.email_utilisateur(reglages, utilisateur_id) if utilisateur_id else None
    if utilisateur_id and email is None:  # compte supprimé entre-temps
        request.session.pop("utilisateur_id", None)
        request.session.pop("email", None)
    return _page(request, "page", email=email, message=request.query_params.get("message"))


@router.get("/inscription", response_class=HTMLResponse)
async def page_inscription(request: Request):
    return _page(request, "inscription", email="")


@router.post("/inscription", response_class=HTMLResponse)
async def inscription(
    request: Request,
    reglages: ReglagesDep,
    email: Champ = "",
    mot_de_passe: Champ = "",
    confirmation: Champ = "",
):
    try:
        if mot_de_passe != confirmation:
            raise ErreurCompte("Les deux mots de passe ne sont pas identiques.")
        utilisateur_id = service.creer_compte(reglages, email, mot_de_passe)
    except ErreurCompte as erreur:
        return _page(request, "inscription", 400, email=email, erreur=str(erreur))
    _ouvrir_session(request, reglages, utilisateur_id, service.normaliser_email(email))
    return _vers("/comptes?message=bienvenue")


@router.get("/connexion", response_class=HTMLResponse)
async def page_connexion(request: Request, suivant: str = "/comptes"):
    return _page(request, "connexion", email="", suivant=_suivant_sur(suivant))


@router.post("/connexion", response_class=HTMLResponse)
async def connexion(
    request: Request,
    reglages: ReglagesDep,
    email: Champ = "",
    mot_de_passe: Champ = "",
    suivant: Champ = "/comptes",
):
    try:
        utilisateur_id = service.authentifier(reglages, email, mot_de_passe)
    except ErreurCompte as erreur:
        return _page(
            request,
            "connexion",
            400,
            email=email,
            suivant=_suivant_sur(suivant),
            erreur=str(erreur),
        )
    _ouvrir_session(request, reglages, utilisateur_id, service.normaliser_email(email))
    return _vers(_suivant_sur(suivant))


@router.post("/deconnexion")
async def deconnexion(request: Request):
    code_postal = request.session.get("code_postal")
    request.session.clear()  # la liste reste dans le compte ; une nouvelle liste vide repart de zéro
    if code_postal:
        request.session["code_postal"] = code_postal
    return _vers("/comptes?message=deconnecte")


@router.get("/mot-de-passe", response_class=HTMLResponse)
async def page_mot_de_passe(request: Request):
    if not request.session.get("utilisateur_id"):
        return _vers("/comptes/connexion?suivant=/comptes/mot-de-passe")
    return _page(request, "mot_de_passe")


@router.post("/mot-de-passe", response_class=HTMLResponse)
async def changer_mot_de_passe(
    request: Request,
    reglages: ReglagesDep,
    actuel: Champ = "",
    nouveau: Champ = "",
    confirmation: Champ = "",
):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion?suivant=/comptes/mot-de-passe")
    try:
        if nouveau != confirmation:
            raise ErreurCompte("Les deux mots de passe ne sont pas identiques.")
        service.changer_mot_de_passe(reglages, utilisateur_id, actuel, nouveau)
    except ErreurCompte as erreur:
        return _page(request, "mot_de_passe", 400, erreur=str(erreur))
    return _vers("/comptes?message=mot_de_passe_change")


@router.get("/mot-de-passe-perdu", response_class=HTMLResponse)
async def page_mot_de_passe_perdu(request: Request):
    return _page(request, "mot_de_passe_perdu", email="", envoye=False)


@router.post("/mot-de-passe-perdu", response_class=HTMLResponse)
async def mot_de_passe_perdu(request: Request, reglages: ReglagesDep, email: Champ = ""):
    await service.demander_reinitialisation(reglages, email, str(request.base_url))
    # Même réponse que l'adresse soit connue ou non : on ne révèle pas qui a un compte.
    return _page(request, "mot_de_passe_perdu", email=email, envoye=True)


@router.get("/reinitialiser", response_class=HTMLResponse)
async def page_reinitialiser(request: Request, reglages: ReglagesDep, jeton: str = ""):
    try:
        service.lire_jeton(reglages, jeton)
    except ErreurCompte as erreur:
        return _page(request, "reinitialiser", 400, jeton="", erreur=str(erreur))
    return _page(request, "reinitialiser", jeton=jeton)


@router.post("/reinitialiser", response_class=HTMLResponse)
async def reinitialiser(
    request: Request,
    reglages: ReglagesDep,
    jeton: Champ = "",
    nouveau: Champ = "",
    confirmation: Champ = "",
):
    try:
        if nouveau != confirmation:
            service.lire_jeton(reglages, jeton)  # un lien invalide passe avant la confirmation
            raise ErreurCompte("Les deux mots de passe ne sont pas identiques.")
        utilisateur_id = service.reinitialiser(reglages, jeton, nouveau)
    except ErreurCompte as erreur:
        lien_valide = "lien" not in str(erreur).lower()
        return _page(
            request, "reinitialiser", 400, jeton=jeton if lien_valide else "", erreur=str(erreur)
        )
    _ouvrir_session(
        request, reglages, utilisateur_id, service.email_utilisateur(reglages, utilisateur_id) or ""
    )
    return _vers("/comptes?message=mot_de_passe_change")
