"""Routes du panier : page de la liste, ajout et suppression de lignes, tableau des prix,
flux SSE des prix et des totaux, et calcul complet en JSON (sans session)."""

import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import ValidationError

from app.collecte.orchestrateur import collecter
from app.config import Reglages, ReglagesDep
from app.contrats import (
    AjoutLigne,
    DemandeTotaux,
    LigneListe,
    Magasin,
    ModeLigne,
    ResultatLigne,
    TotauxReponse,
)
from app.gabarits import rendre, templates
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide
from app.magasins.service import magasins_proches
from app.panier import calcul, service, ticket
from app.sources.registre import sources_actives

router = APIRouter(tags=["panier"])
logger = logging.getLogger(__name__)
TAILLE_MAX_TICKET = 10 * 1024 * 1024


async def comparer(
    lignes: list[LigneListe], magasins: list[Magasin], reglages: Reglages
) -> AsyncIterator[ResultatLigne]:
    """Résultats complétés (sous-totaux), dans l'ordre d'arrivée."""
    par_id = {ligne.id: ligne for ligne in lignes}
    async for resultat in collecter(lignes, magasins, sources_actives(reglages), reglages):
        yield calcul.completer(par_id[resultat.ligne_id], resultat)


def _liste_maj(
    request: Request, reglages: Reglages, erreur: str | None = None, ticket_fini: bool = False
) -> HTMLResponse:
    lignes = service.lister(reglages, service.proprietaire(request))
    return templates.TemplateResponse(
        request,
        "panier/_liste_maj.html",
        {"lignes": lignes, "erreur": erreur, "ticket_fini": ticket_fini},
    )


@router.get("/panier", response_class=HTMLResponse)
async def page_panier(request: Request, reglages: ReglagesDep):
    code_postal = request.session.get("code_postal")
    if not code_postal:
        return RedirectResponse("/", status_code=303)
    lignes = service.lister(reglages, service.proprietaire(request))
    return templates.TemplateResponse(
        request, "panier/page.html", {"code_postal": code_postal, "lignes": lignes}
    )


@router.post("/panier/lignes", response_class=HTMLResponse)
async def ajouter_ligne(
    request: Request,
    reglages: ReglagesDep,
    mode: Annotated[str, Form()] = "",
    recherche: Annotated[str, Form()] = "",
    ean: Annotated[str, Form()] = "",
    libelle: Annotated[str, Form()] = "",
    quantite: Annotated[str, Form()] = "1",
):
    try:
        ajout = AjoutLigne(
            mode=mode,
            ean=ean.strip() or None,
            recherche=recherche,
            libelle=libelle or None,
            quantite=quantite or 1,
        )
    except ValidationError:
        return _liste_maj(request, reglages, erreur="Article non ajouté : vérifiez la quantité.")
    service.ajouter(reglages, service.proprietaire(request), ajout)
    return _liste_maj(request, reglages)


@router.post("/panier/ticket", response_class=HTMLResponse)
async def lire_ticket(request: Request, image: UploadFile):
    """Photo d'un ticket de caisse → articles lus, à vérifier avant de les ajouter."""
    contexte: dict = {"articles": [], "erreur": None}
    contenu = await image.read(TAILLE_MAX_TICKET + 1)
    if not (image.content_type or "").startswith("image/") or len(contenu) > TAILLE_MAX_TICKET:
        contexte["erreur"] = "Envoyez une photo du ticket (10 Mo au plus)."
    else:
        try:
            contexte["articles"] = ticket.analyser(
                await asyncio.to_thread(ticket.lire_texte, contenu)
            )
        except Exception:
            logger.exception("Lecture du ticket impossible")
        if not contexte["articles"]:
            contexte["erreur"] = "Aucun article lu sur ce ticket : essayez une photo plus nette."
    return templates.TemplateResponse(request, "panier/_ticket.html", contexte)


@router.post("/panier/ticket/ajouter", response_class=HTMLResponse)
async def ajouter_ticket(
    request: Request,
    reglages: ReglagesDep,
    recherche: Annotated[list[str], Form()] = [],  # noqa: B006 (FastAPI copie la valeur)
    quantite: Annotated[list[str], Form()] = [],  # noqa: B006
):
    """Ajoute les articles du ticket gardés et corrigés par l'utilisateur."""
    proprietaire = service.proprietaire(request)
    ignores = 0
    for texte, nombre in zip(recherche, quantite, strict=False):
        if not texte.strip():
            continue
        try:
            ajout = AjoutLigne(
                mode=ModeLigne.EQUIVALENT, recherche=texte.strip(), quantite=nombre or 1
            )
        except ValidationError:
            ignores += 1
            continue
        service.ajouter(reglages, proprietaire, ajout)
    erreur = f"{ignores} article(s) non ajouté(s) : vérifiez la quantité." if ignores else None
    return _liste_maj(request, reglages, erreur=erreur, ticket_fini=True)


@router.delete("/panier/lignes/{ligne_id}", response_class=HTMLResponse)
async def supprimer_ligne(request: Request, ligne_id: int, reglages: ReglagesDep):
    service.supprimer(reglages, service.proprietaire(request), ligne_id)
    return _liste_maj(request, reglages)


@router.get("/panier/resultats", response_class=HTMLResponse)
async def tableau_resultats(request: Request, reglages: ReglagesDep):
    """Tableau vide (articles × magasins) qui se remplit ensuite par le flux SSE."""
    lignes = service.lister(reglages, service.proprietaire(request, creer=False))
    code_postal = request.session.get("code_postal", "")
    contexte: dict = {"lignes": lignes, "magasins": [], "message": None}
    if not lignes:
        contexte["message"] = "Ajoutez au moins un article à votre liste."
    else:
        try:
            contexte["magasins"] = (
                await magasins_proches(code_postal, reglages, request.session.get("rayon_km"))
            ).magasins
        except (CodePostalInvalide, CodePostalInconnu):
            contexte["message"] = "Choisissez d'abord votre code postal."
        if not contexte["magasins"] and not contexte["message"]:
            contexte["message"] = "Aucun magasin trouvé autour de ce code postal."
    return templates.TemplateResponse(request, "panier/_resultats.html", contexte)


@router.get("/panier/prix/flux", response_class=EventSourceResponse)
async def flux_prix(request: Request, reglages: ReglagesDep) -> AsyncIterable[ServerSentEvent]:
    """Une case du tableau par événement « prix-<ligne>-<magasin> », le total du magasin par
    « total-<magasin> », le classement par « resume », puis « fin » (le navigateur ferme alors)."""
    lignes = service.lister(reglages, service.proprietaire(request, creer=False))
    try:
        magasins = (
            await magasins_proches(
                request.session.get("code_postal", ""), reglages, request.session.get("rayon_km")
            )
        ).magasins
    except (CodePostalInvalide, CodePostalInconnu):
        magasins = []

    resultats: list[ResultatLigne] = []
    if lignes and magasins:
        lignes_par_id = {ligne.id: ligne for ligne in lignes}
        magasins_par_id = {magasin.id: magasin for magasin in magasins}
        async for resultat in comparer(lignes, magasins, reglages):
            resultats.append(resultat)
            yield ServerSentEvent(
                event=f"prix-{resultat.ligne_id}-{resultat.magasin_id}",
                raw_data=rendre(
                    "panier/_case.html",
                    resultat=resultat,
                    ligne=lignes_par_id[resultat.ligne_id],
                    magasin=magasins_par_id[resultat.magasin_id],
                ),
            )
            total = next(
                t
                for t in calcul.totaux(lignes, magasins, resultats)
                if t.magasin.id == resultat.magasin_id
            )
            yield ServerSentEvent(
                event=f"total-{resultat.magasin_id}",
                raw_data=rendre("panier/_total.html", total=total),
            )
        yield ServerSentEvent(
            event="resume",
            raw_data=rendre(
                "panier/_resume.html", totaux=calcul.totaux(lignes, magasins, resultats)
            ),
        )
    yield ServerSentEvent(event="fin", raw_data="fin")


@router.post("/api/panier/totaux", response_model=TotauxReponse)
async def api_totaux(demande: DemandeTotaux, reglages: ReglagesDep):
    """Calcul complet sans session : code postal + lignes → prix et totaux par magasin."""
    try:
        magasins = (await magasins_proches(demande.code_postal, reglages)).magasins
    except CodePostalInvalide as erreur:
        raise HTTPException(422, "Code postal invalide : 5 chiffres attendus") from erreur
    except CodePostalInconnu as erreur:
        raise HTTPException(404, "Code postal introuvable") from erreur
    lignes = [
        LigneListe(
            id=numero,
            mode=ajout.mode,
            ean=ajout.ean,
            recherche=ajout.recherche,
            libelle=ajout.libelle or ajout.recherche,
            quantite=ajout.quantite,
        )
        for numero, ajout in enumerate(demande.lignes, start=1)
    ]
    resultats = [resultat async for resultat in comparer(lignes, magasins, reglages)]
    return TotauxReponse(
        lignes=lignes,
        magasins=magasins,
        resultats=resultats,
        totaux=calcul.totaux(lignes, magasins, resultats),
    )
