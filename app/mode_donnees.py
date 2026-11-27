"""Mode des données, choisi par chaque visiteur (gardé dans sa session).

- « demo » : tous les magasins, prix fictifs (toujours marqués), aucune requête aux extensions Edge.
- « reel » : seulement les drives répertoriés (app/drives/points_retrait.json), prix relevés par les
  extensions Edge, aucune donnée fictive.
Valeur par défaut : MODE_DONNEES_DEFAUT dans `.env` (« demo » si absent).
"""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

DEMO = "demo"
REEL = "reel"
MODES = {DEMO: "Démo (prix fictifs)", REEL: "Données réelles (drives)"}

router = APIRouter(tags=["mode"])


def mode_donnees(request: Request) -> str:
    choix = request.session.get("mode_donnees")
    if choix in MODES:
        return choix
    defaut = request.app.state.reglages.mode_donnees_defaut.strip().lower()
    return defaut if defaut in MODES else DEMO


def est_reel(request: Request) -> bool:
    return mode_donnees(request) == REEL


def _chemin_sur(suivant: str) -> str:
    """Page où revenir : seulement un chemin de ce site (pas de redirection ouverte)."""
    if suivant.startswith("/") and not suivant.startswith("//") and "\\" not in suivant:
        return suivant
    return "/"


@router.post("/mode-donnees")
async def changer_mode(
    request: Request,
    mode: Annotated[str, Form()] = DEMO,
    suivant: Annotated[str, Form()] = "/",
):
    if mode in MODES:
        request.session["mode_donnees"] = mode
    return RedirectResponse(_chemin_sur(suivant), status_code=303)
