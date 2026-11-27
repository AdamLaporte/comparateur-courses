"""Routes des comptes (lot 2). BOUCHON : une page d'attente seulement.

Routes prévues : /comptes/inscription, /comptes/connexion, /comptes/deconnexion, /comptes/favoris.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.gabarits import templates

router = APIRouter(prefix="/comptes", tags=["comptes"])


@router.get("", response_class=HTMLResponse)
async def page_compte(request: Request):
    return templates.TemplateResponse(request, "comptes/page.html", {})
