"""Routes : suggestions d'articles (fragment HTMX et JSON)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import ReglagesDep
from app.contrats import Produit
from app.gabarits import templates
from app.produits.service import rechercher

router = APIRouter(tags=["produits"])


@router.get("/produits/recherche", response_class=HTMLResponse)
async def suggestions(request: Request, reglages: ReglagesDep, q: str = ""):
    produits = await rechercher(q, reglages)
    return templates.TemplateResponse(
        request, "produits/_suggestions.html", {"q": q.strip(), "produits": produits}
    )


@router.get("/api/produits", response_model=list[Produit])
async def api_produits(q: str, reglages: ReglagesDep):
    return await rechercher(q, reglages)
