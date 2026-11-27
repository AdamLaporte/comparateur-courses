"""Routes du panier : page de la liste, ajout et suppression de lignes, tableau des prix,
flux SSE des prix et des totaux, et calcul complet en JSON (sans session)."""

import asyncio
import logging
import re
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import ValidationError

from app.collecte.orchestrateur import collecter
from app.comptes import cagnotte
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
from app.produits.service import rechercher
from app.sources.registre import sources_actives

router = APIRouter(tags=["panier"])
logger = logging.getLogger(__name__)
TAILLE_MAX_TICKET = 10 * 1024 * 1024
_UNITES = {"g", "kg", "l", "cl", "ml", "x", "lot", "de"}
INEXISTANT = "inexistant"  # valeur du choix « Inexistant en magasins » dans le formulaire du ticket


def comparables(lignes: list[LigneListe]) -> list[LigneListe]:
    """Lignes à comparer : un article « inexistant en magasins » reste dans la liste, sans prix."""
    return [ligne for ligne in lignes if ligne.mode != ModeLigne.INEXISTANT]


async def correspondances(recherche: str, reglages: Reglages) -> list:
    """Produits du catalogue qui correspondent à un article lu sur le ticket (le premier est proposé).
    Le texte d'un ticket est approximatif : on réessaie sans les tailles (« 400 g », « 1 l »), puis
    avec le premier mot seul s'il est assez long."""
    mots = [m for m in recherche.split() if not re.search(r"\d", m) and m.lower() not in _UNITES]
    essais = dict.fromkeys(
        e for e in (recherche, " ".join(mots), mots[0] if mots and len(mots[0]) >= 4 else "") if e
    )
    for essai in essais:
        try:
            produits = [p for p in await rechercher(essai, reglages, limite=5) if p.ean]
        except Exception:
            logger.exception("Recherche impossible pour « %s »", essai)
            continue
        if produits:
            return produits
    return []


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
    code_postal = request.session.get("code_postal", "")
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
async def lire_ticket(request: Request, reglages: ReglagesDep, image: UploadFile):
    """Photo d'un ticket de caisse → articles lus, chacun rapproché d'un produit vendu en magasin,
    à vérifier avant de les ajouter."""
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
    contexte["articles"] = [
        (recherche, quantite, await correspondances(recherche, reglages))
        for recherche, quantite in contexte["articles"]
    ]
    return templates.TemplateResponse(request, "panier/_ticket.html", contexte)


@router.get("/panier/ticket/correspondances", response_class=HTMLResponse)
async def nouvelles_correspondances(
    request: Request, reglages: ReglagesDep, recherche: str = "", n: int = 0
):
    """Après correction du libellé d'un article du ticket : nouvelle liste de produits."""
    return templates.TemplateResponse(
        request,
        "panier/_ticket_choix.html",
        {"n": n, "recherche": recherche, "produits": await correspondances(recherche, reglages)},
    )


@router.post("/panier/ticket/ajouter", response_class=HTMLResponse)
async def ajouter_ticket(
    request: Request,
    reglages: ReglagesDep,
    recherche: Annotated[list[str], Form()] = [],  # noqa: B006 (FastAPI copie la valeur)
    quantite: Annotated[list[str], Form()] = [],  # noqa: B006
    choix: Annotated[list[str], Form()] = [],  # noqa: B006
):
    """Ajoute les articles du ticket gardés par l'utilisateur : chacun est soit le produit choisi
    (« <ean>|<libellé> »), soit « inexistant » (gardé dans la liste mais jamais comparé)."""
    proprietaire = service.proprietaire(request)
    ignores = 0
    for texte, nombre, produit in zip(recherche, quantite, choix, strict=False):
        if not texte.strip():
            continue
        ean, _, libelle = produit.partition("|")
        try:
            if produit != INEXISTANT and ean.isdigit():
                ajout = AjoutLigne(
                    mode=ModeLigne.PRODUIT,
                    ean=ean,
                    recherche=texte.strip(),
                    libelle=libelle.strip() or None,
                    quantite=nombre or 1,
                )
            else:
                ajout = AjoutLigne(
                    mode=ModeLigne.INEXISTANT, recherche=texte.strip(), quantite=nombre or 1
                )
        except ValidationError:
            ignores += 1
            continue
        service.ajouter(reglages, proprietaire, ajout)
    erreur = f"{ignores} article(s) non ajouté(s) : vérifiez la quantité." if ignores else None
    return _liste_maj(request, reglages, erreur=erreur, ticket_fini=True)


@router.post("/panier/lignes/mode", response_class=HTMLResponse)
async def changer_mode_liste(
    request: Request, reglages: ReglagesDep, mode: Annotated[str, Form()] = ""
):
    """Toute la liste en « le moins cher » (mode=equivalent), ou retour aux produits choisis."""
    if mode in (ModeLigne.PRODUIT, ModeLigne.EQUIVALENT):
        service.changer_mode_tout(reglages, service.proprietaire(request), ModeLigne(mode))
    return _liste_maj(request, reglages)


@router.post("/panier/lignes/{ligne_id}/mode", response_class=HTMLResponse)
async def changer_mode_ligne(
    request: Request, ligne_id: int, reglages: ReglagesDep, mode: Annotated[str, Form()] = ""
):
    """Un article : « produit précis » ↔ « le moins cher »."""
    if mode in (ModeLigne.PRODUIT, ModeLigne.EQUIVALENT):
        service.changer_mode(reglages, service.proprietaire(request), ligne_id, ModeLigne(mode))
    return _liste_maj(request, reglages)


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
    elif not comparables(lignes):
        contexte["message"] = "Aucun article de votre liste n'existe en magasin : rien à comparer."
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
    « total-<magasin> », le classement par « resume », puis « fin » (le navigateur ferme alors).
    Les articles « inexistant en magasins » ne sont ni cherchés ni comptés."""
    lignes = comparables(service.lister(reglages, service.proprietaire(request, creer=False)))
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
        totaux = calcul.totaux(lignes, magasins, resultats)
        utilisateur_id = request.session.get("utilisateur_id")
        economie = cagnotte.preparer(reglages, utilisateur_id, totaux) if utilisateur_id else None
        yield ServerSentEvent(
            event="resume",
            raw_data=rendre(
                "panier/_resume.html",
                totaux=totaux,
                economie=economie,
                prix_fictifs=any(r.prix and r.prix.est_fictif for r in resultats),
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
    lignes = comparables(lignes)
    resultats = [resultat async for resultat in comparer(lignes, magasins, reglages)]
    return TotauxReponse(
        lignes=lignes,
        magasins=magasins,
        resultats=resultats,
        totaux=calcul.totaux(lignes, magasins, resultats),
    )
