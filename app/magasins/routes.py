"""Routes : accueil (saisie du code postal) et magasins proches (page HTML et JSON)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import ReglagesDep
from app.contrats import MagasinsReponse
from app.gabarits import templates
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide
from app.magasins.service import magasins_proches

router = APIRouter(tags=["magasins"])

MESSAGE_INVALIDE = "Saisissez un code postal à 5 chiffres, par exemple 35170."
MESSAGE_INCONNU = "Ce code postal est introuvable pour l'instant. Vérifiez-le ou réessayez."


@router.get("/", response_class=HTMLResponse)
async def accueil(request: Request):
    return templates.TemplateResponse(
        request, "magasins/accueil.html", {"code_postal": request.session.get("code_postal", "")}
    )


@router.get("/magasins", response_class=HTMLResponse)
async def page_magasins(request: Request, reglages: ReglagesDep, code_postal: str = ""):
    try:
        reponse = await magasins_proches(code_postal, reglages)
    except (CodePostalInvalide, CodePostalInconnu) as erreur:
        message = MESSAGE_INVALIDE if isinstance(erreur, CodePostalInvalide) else MESSAGE_INCONNU
        return templates.TemplateResponse(
            request, "magasins/accueil.html", {"code_postal": code_postal, "erreur": message}
        )
    request.session["code_postal"] = reponse.code_postal
    return templates.TemplateResponse(request, "magasins/liste.html", {"reponse": reponse})


@router.get("/api/magasins", response_model=MagasinsReponse)
async def api_magasins(code_postal: str, reglages: ReglagesDep):
    try:
        return await magasins_proches(code_postal, reglages)
    except CodePostalInvalide as erreur:
        raise HTTPException(422, MESSAGE_INVALIDE) from erreur
    except CodePostalInconnu as erreur:
        raise HTTPException(404, MESSAGE_INCONNU) from erreur
