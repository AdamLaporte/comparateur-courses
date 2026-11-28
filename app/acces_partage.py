"""Accès au site HTTPS privé et séparation des appels des extensions."""

import base64
import re
import secrets

from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Reglages

ROUTES_COLLECTE = re.compile(
    r"/api/drives/(?:(?:coursesu|intermarche|carrefour|leclerc)-[a-z0-9_-]+/(?:connexion|prendre)"
    r"|enseignes/(?:coursesu|intermarche|carrefour|leclerc)"
    r"/(?:connexion|prendre|points-retrait|inscrire-point-retrait)"
    r"|taches/[0-9]+/depot)"
)


class AccesPartage:
    def __init__(self, app: ASGIApp, reglages: Reglages) -> None:
        self.app = app
        self.reglages = reglages

    def _identifie(self, autorisation: str) -> bool:
        type_auth, _, code = autorisation.partition(" ")
        if type_auth.lower() != "basic":
            return False
        try:
            identifiant, _, mot_de_passe = (
                base64.b64decode(code, validate=True).decode().partition(":")
            )
        except ValueError:
            return False
        attendu = self.reglages.site_partage_comptes.get(identifiant)
        return bool(
            attendu
            and secrets.compare_digest(mot_de_passe.encode(), attendu.get_secret_value().encode())
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        requete = Request(scope)
        origine = self.reglages.site_partage_origine
        if f"{requete.url.scheme}://{requete.url.netloc}" != origine:
            reponse = PlainTextResponse("Utilisez l’adresse HTTPS du comparateur.", status_code=400)
        elif requete.method == "POST" and ROUTES_COLLECTE.fullmatch(requete.url.path):
            await self.app(scope, receive, send)
            return
        elif not self._identifie(requete.headers.get("authorization", "")):
            reponse = PlainTextResponse(
                "Accès réservé au comparateur.",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Comparateur", charset="UTF-8"'},
            )
        elif (
            requete.method not in ("GET", "HEAD", "OPTIONS")
            and requete.headers.get("origin", origine) != origine
        ):
            reponse = PlainTextResponse("Origine non autorisée.", status_code=403)
        else:
            await self.app(scope, receive, send)
            return
        await reponse(scope, receive, send)
