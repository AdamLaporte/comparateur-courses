"""Routes : accueil (ville, code postal ou position, et rayon) et magasins proches (page HTML et JSON)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import ReglagesDep
from app.contrats import MagasinsReponse
from app.gabarits import templates
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide
from app.magasins.service import magasins_proches
from app.panier import service as panier

router = APIRouter(tags=["magasins"])

MESSAGE_INVALIDE = "Saisissez une ville ou un code postal à 5 chiffres, par exemple Bruz ou 35170."
MESSAGE_INCONNU = "Ce lieu est introuvable pour l'instant. Vérifiez-le ou réessayez."
RAYONS_KM = (2, 5, 10, 20, 30)


def lire_rayon(texte: str | float | None) -> float | None:
    """Rayon choisi en km, ou None pour « les plus proches » (valeur vide ou hors limites)."""
    try:
        rayon = float(texte)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return rayon if 0 < rayon <= 50 else None


def nb_articles(request: Request, reglages) -> int:
    """Taille de la liste en cours (0 sans session) : pour proposer de la reprendre."""
    return len(panier.lister(reglages, panier.proprietaire(request, creer=False)))


@router.get("/", response_class=HTMLResponse)
async def accueil(request: Request, reglages: ReglagesDep):
    return templates.TemplateResponse(
        request,
        "magasins/accueil.html",
        {
            "code_postal": request.session.get("code_postal", ""),
            "rayon_km": request.session.get("rayon_km"),
            "rayons": RAYONS_KM,
            "nb_articles": nb_articles(request, reglages),
        },
    )


@router.get("/magasins", response_class=HTMLResponse)
async def page_magasins(
    request: Request, reglages: ReglagesDep, code_postal: str = "", rayon_km: str = ""
):
    rayon = lire_rayon(rayon_km)
    try:
        reponse = await magasins_proches(code_postal, reglages, rayon)
    except (CodePostalInvalide, CodePostalInconnu) as erreur:
        message = MESSAGE_INVALIDE if isinstance(erreur, CodePostalInvalide) else MESSAGE_INCONNU
        contexte = {
            "code_postal": code_postal,
            "rayon_km": rayon,
            "rayons": RAYONS_KM,
            "erreur": message,
        }
        return templates.TemplateResponse(request, "magasins/accueil.html", contexte)
    request.session["code_postal"] = reponse.code_postal
    request.session["rayon_km"] = rayon
    return templates.TemplateResponse(
        request,
        "magasins/liste.html",
        {"reponse": reponse, "nb_articles": nb_articles(request, reglages)},
    )


@router.get("/api/magasins", response_model=MagasinsReponse)
async def api_magasins(code_postal: str, reglages: ReglagesDep, rayon_km: float | None = None):
    try:
        return await magasins_proches(code_postal, reglages, lire_rayon(rayon_km))
    except CodePostalInvalide as erreur:
        raise HTTPException(422, MESSAGE_INVALIDE) from erreur
    except CodePostalInconnu as erreur:
        raise HTTPException(404, MESSAGE_INCONNU) from erreur
