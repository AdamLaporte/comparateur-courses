"""Point d'entrée : crée l'application FastAPI (fichier partagé, ne bouge plus).

Tous les routers sont inclus dès le départ : aucun lot n'a besoin de modifier ce fichier.
Lancer : uv run uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import db
from app.comptes import routes as routes_comptes
from app.config import Reglages
from app.drives.routes import router as routes_drives
from app.gabarits import templates
from app.magasins import routes as routes_magasins
from app.panier import routes as routes_panier
from app.panier.service import migrer as migrer_panier
from app.produits import routes as routes_produits

DOSSIER_APP = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def _est_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def creer_app(reglages: Reglages | None = None) -> FastAPI:
    reglages = reglages or Reglages()

    @asynccontextmanager
    async def cycle_de_vie(app: FastAPI):
        db.initialiser(reglages.db_path)
        migrer_panier(reglages.db_path)
        yield

    app = FastAPI(
        title="Comparateur de courses",
        description="Compare le prix d'un panier de courses entre les supermarchés proches.",
        lifespan=cycle_de_vie,
    )
    app.state.reglages = reglages
    app.add_middleware(
        SessionMiddleware, secret_key=reglages.secret_key, same_site="lax", max_age=30 * 24 * 3600
    )
    app.mount("/static", StaticFiles(directory=DOSSIER_APP / "static"), name="static")

    for module in (routes_magasins, routes_produits, routes_panier, routes_comptes):
        app.include_router(module.router)

    app.include_router(routes_drives)

    # Jamais d'erreur brute à l'utilisateur : page d'erreur lisible pour le HTML, message court en JSON.
    @app.exception_handler(StarletteHTTPException)
    async def erreur_http(request: Request, exc: StarletteHTTPException):
        if _est_api(request):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        message = "Cette page n'existe pas." if exc.status_code == 404 else "Requête impossible."
        return templates.TemplateResponse(
            request, "erreur.html", {"message": message}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def erreur_validation(request: Request, exc: RequestValidationError):
        if _est_api(request):
            return JSONResponse({"detail": exc.errors()}, status_code=422)
        return templates.TemplateResponse(
            request, "erreur.html", {"message": "Données saisies incorrectes."}, status_code=422
        )

    @app.exception_handler(Exception)
    async def erreur_interne(request: Request, exc: Exception):
        logger.exception("Erreur interne sur %s", request.url.path)
        if _est_api(request):
            return JSONResponse({"detail": "Erreur interne, réessayez."}, status_code=500)
        return templates.TemplateResponse(
            request,
            "erreur.html",
            {"message": "Un problème est survenu de notre côté. Réessayez dans un instant."},
            status_code=500,
        )

    return app


app = creer_app()
