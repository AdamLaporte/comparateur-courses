"""Routes des comptes (facultatifs : tout le site marche sans compte).

/comptes                      page du compte (ou invitation à se connecter)
/comptes/inscription          créer un compte
/comptes/connexion            se connecter (rattache la liste faite sans compte)
/comptes/deconnexion          se déconnecter (POST)
/comptes/mot-de-passe         changer son mot de passe (connecté)
/comptes/mot-de-passe-perdu   recevoir un lien de réinitialisation
/comptes/reinitialiser        choisir un nouveau mot de passe depuis le lien
/comptes/favoris              articles favoris : ajout depuis la liste, ajout à la liste, retrait
/comptes/maison               enregistrer ou retirer sa « maison » (code postal)
"""

import html
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.comptes import cagnotte, service
from app.comptes.service import ErreurCompte
from app.config import ReglagesDep
from app.contrats import AjoutLigne
from app.gabarits import templates
from app.panier import service as service_panier

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


async def _ouvrir_session(request: Request, reglages, utilisateur_id: int, email: str) -> None:
    service.rattacher_liste(reglages, request.session.get("sid"), utilisateur_id)
    request.session.pop("sid", None)
    request.session["utilisateur_id"] = utilisateur_id
    request.session["email"] = email
    maison = await service.maison_pour_session(reglages, utilisateur_id)
    if maison:
        request.session["maison"] = maison
        request.session.setdefault("code_postal", maison["code_postal"])


@router.get("", response_class=HTMLResponse)
async def page_compte(request: Request, reglages: ReglagesDep):
    utilisateur_id = request.session.get("utilisateur_id")
    email = service.email_utilisateur(reglages, utilisateur_id) if utilisateur_id else None
    if utilisateur_id and email is None:  # compte supprimé entre-temps
        request.session.pop("utilisateur_id", None)
        request.session.pop("email", None)
    return _page(
        request,
        "page",
        email=email,
        maison=request.session.get("maison") if email else None,
        solde_cagnotte=cagnotte.solde(reglages, utilisateur_id) if email else 0,
        message=request.query_params.get("message"),
    )


@router.post("/cagnotte")
async def enregistrer_economie(
    request: Request, reglages: ReglagesDep, comparaison: Champ = "", magasin_id: Champ = ""
):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion?suivant=/panier")
    ok = cagnotte.enregistrer(reglages, utilisateur_id, comparaison, magasin_id)
    return _vers(f"/comptes?message={'cagnotte_ajoutee' if ok else 'cagnotte_indisponible'}")


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
    await _ouvrir_session(request, reglages, utilisateur_id, service.normaliser_email(email))
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
    await _ouvrir_session(request, reglages, utilisateur_id, service.normaliser_email(email))
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
    await _ouvrir_session(
        request, reglages, utilisateur_id, service.email_utilisateur(reglages, utilisateur_id) or ""
    )
    return _vers("/comptes?message=mot_de_passe_change")


# --- Articles favoris ---


def _ajouter_a_la_liste(reglages, utilisateur_id: int, favori: dict) -> None:
    try:
        ajout = AjoutLigne(
            mode=favori["mode"],
            ean=favori["ean"],
            recherche=favori["recherche"],
            libelle=favori["libelle"],
        )
    except ValidationError:
        return
    service_panier.ajouter(reglages, f"utilisateur:{utilisateur_id}", ajout)


@router.get("/favoris", response_class=HTMLResponse)
async def page_favoris(request: Request, reglages: ReglagesDep):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion?suivant=/comptes/favoris")
    return _page(
        request,
        "favoris",
        favoris=service.lister_favoris(reglages, utilisateur_id),
        message=request.query_params.get("message"),
    )


@router.post("/favoris/depuis-ligne/{ligne_id}", response_class=HTMLResponse)
async def favori_depuis_ligne(request: Request, reglages: ReglagesDep, ligne_id: int):
    """Bouton « ☆ Favori » d'une ligne de la liste (HTMX) : rend l'étiquette « ★ En favori »."""
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return HTMLResponse('<a class="note" href="/comptes/connexion">Connectez-vous</a>')
    lignes = service_panier.lister(reglages, f"utilisateur:{utilisateur_id}")
    ligne = next((lg for lg in lignes if lg.id == ligne_id), None)
    if ligne is None:
        return HTMLResponse("", status_code=404)
    try:
        service.ajouter_favori(
            reglages, utilisateur_id, ligne.mode.value, ligne.ean, ligne.recherche, ligne.libelle
        )
    except ErreurCompte as erreur:
        return HTMLResponse(f'<span class="erreur">{html.escape(str(erreur))}</span>')
    return HTMLResponse('<span class="favori">★ En favori</span>')


@router.post("/favoris/{favori_id}/ajouter-a-la-liste")
async def favori_vers_liste(request: Request, reglages: ReglagesDep, favori_id: int):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion?suivant=/comptes/favoris")
    favori = service.favori(reglages, utilisateur_id, favori_id)
    if favori is not None:
        _ajouter_a_la_liste(reglages, utilisateur_id, favori)
    return _vers("/comptes/favoris?message=ajoute")


@router.post("/favoris/tout-ajouter")
async def favoris_vers_liste(request: Request, reglages: ReglagesDep):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion?suivant=/comptes/favoris")
    for favori in service.lister_favoris(reglages, utilisateur_id):
        _ajouter_a_la_liste(reglages, utilisateur_id, favori)
    return _vers(
        "/panier" if request.session.get("code_postal") else "/comptes/favoris?message=tous"
    )


@router.post("/favoris/{favori_id}/supprimer")
async def supprimer_favori(request: Request, reglages: ReglagesDep, favori_id: int):
    utilisateur_id = request.session.get("utilisateur_id")
    if utilisateur_id:
        service.supprimer_favori(reglages, utilisateur_id, favori_id)
    return _vers("/comptes/favoris?message=retire")


# --- Maison ---


@router.post("/maison", response_class=HTMLResponse)
async def enregistrer_maison(
    request: Request, reglages: ReglagesDep, code_postal: Champ = "", suivant: Champ = "/comptes"
):
    utilisateur_id = request.session.get("utilisateur_id")
    if not utilisateur_id:
        return _vers("/comptes/connexion")
    try:
        request.session["maison"] = await service.enregistrer_maison(
            reglages, utilisateur_id, code_postal
        )
    except ErreurCompte as erreur:
        return _page(
            request,
            "page",
            400,
            email=service.email_utilisateur(reglages, utilisateur_id),
            maison=request.session.get("maison"),
            solde_cagnotte=cagnotte.solde(reglages, utilisateur_id),
            erreur_maison=str(erreur),
            code_postal_saisi=code_postal,
        )
    suivant = _suivant_sur(suivant)
    return _vers("/comptes?message=maison" if suivant == "/comptes" else suivant)


@router.post("/maison/supprimer")
async def supprimer_maison(request: Request, reglages: ReglagesDep):
    utilisateur_id = request.session.get("utilisateur_id")
    if utilisateur_id:
        service.supprimer_maison(reglages, utilisateur_id)
        request.session.pop("maison", None)
    return _vers("/comptes?message=maison_retiree")
