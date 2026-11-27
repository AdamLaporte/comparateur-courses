"""Routes du panier : page de la liste, ajout et suppression de lignes, tableau des prix,
flux SSE des prix et des totaux, et calcul complet en JSON (sans session)."""

import asyncio
import json
import logging
import re
from collections import Counter
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
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
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide, localisation_proche
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
    """Lignes à comparer : toutes. Un article « inexistant » dans notre catalogue est cherché sur la
    site des drives répertoriés par les extensions (app/drives/comparaison.py)."""
    return list(lignes)


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
    lignes: list[LigneListe],
    magasins: list[Magasin],
    reglages: Reglages,
    *,
    suivre_edge: bool = False,
) -> AsyncIterator[ResultatLigne]:
    """Résultats complétés (sous-totaux), dans l'ordre d'arrivée."""
    par_id = {ligne.id: ligne for ligne in lignes}
    async for resultat in collecter(
        lignes, magasins, sources_actives(reglages), reglages, suivre_edge=suivre_edge
    ):
        yield calcul.completer(par_id[resultat.ligne_id], resultat)


def _liste_maj(
    request: Request,
    reglages: Reglages,
    erreur: str | None = None,
    ticket_fini: bool = False,
    toast: dict | None = None,
    vider_suggestions: bool = False,
) -> HTMLResponse:
    """La liste à jour, plus en option : un message (toast) avec ou sans « Annuler », les suggestions
    vidées (après un ajout) et le ticket lu refermé."""
    cle = service.cle_liste(request, reglages)
    lignes = service.lister(reglages, cle)
    return templates.TemplateResponse(
        request,
        "panier/_liste_maj.html",
        {
            "lignes": lignes,
            "erreur": erreur,
            "ticket_fini": ticket_fini,
            "toast": toast,
            "liste_toast": "principale" if cle == service.proprietaire(request) else cle,
            "vider_suggestions": vider_suggestions,
        },
    )


def _pour_annuler(lignes: list[LigneListe]) -> str:
    """Les lignes retirées, en JSON, pour le bouton « Annuler » du message."""
    champs = {"id", "mode", "ean", "recherche", "libelle", "quantite"}
    return json.dumps([ligne.model_dump(mode="json", include=champs) for ligne in lignes])


def _depuis_annulation(texte: str) -> list[LigneListe]:
    """Lignes renvoyées par « Annuler », revérifiées comme un ajout (on ignore les invalides)."""
    try:
        donnees = json.loads(texte)
    except ValueError:
        return []
    lignes = []
    for d in donnees[:200] if isinstance(donnees, list) else []:
        try:
            ajout = AjoutLigne(
                mode=d["mode"],
                ean=d.get("ean"),
                recherche=d["recherche"],
                libelle=d.get("libelle"),
                quantite=d.get("quantite", 1),
            )
            lignes.append(
                LigneListe(
                    id=int(d["id"]),
                    mode=ajout.mode,
                    ean=ajout.ean,
                    recherche=ajout.recherche.strip(),
                    libelle=(ajout.libelle or ajout.recherche).strip(),
                    quantite=ajout.quantite,
                )
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            continue
    return lignes


@router.get("/panier", response_class=HTMLResponse)
async def page_panier(request: Request, reglages: ReglagesDep):
    code_postal = request.session.get("code_postal", "")
    compte = service.proprietaire(request)
    active = service.cle_liste(request, reglages)
    listes = service.listes(reglages, compte)
    lignes = service.lister(reglages, active)
    return templates.TemplateResponse(
        request,
        "panier/page.html",
        {
            "code_postal": code_postal,
            "lignes": lignes,
            "listes_courses": {
                "principale" if cle == compte else cle: nom for cle, nom in listes.items()
            },
            "liste_active": "principale" if active == compte else active,
            "erreur_liste": request.query_params.get("erreur") == "nom",
            "comparer": bool(
                code_postal and lignes and request.query_params.get("comparer") == "1"
            ),
        },
    )


@router.post("/panier/listes")
async def creer_liste(request: Request, reglages: ReglagesDep, nom: Annotated[str, Form()]):
    try:
        cle = service.enregistrer_liste(reglages, service.proprietaire(request), nom)
    except ValueError:
        return RedirectResponse("/panier?erreur=nom", status_code=303)
    request.session["liste_active"] = cle
    return RedirectResponse("/panier", status_code=303)


@router.post("/panier/listes/selection")
async def selectionner_liste(
    request: Request, reglages: ReglagesDep, liste: Annotated[str, Form()]
):
    compte = service.proprietaire(request)
    if liste != "principale" and liste not in service.listes(reglages, compte):
        raise HTTPException(404, "Liste introuvable.")
    request.session["liste_active"] = liste
    return RedirectResponse("/panier", status_code=303)


@router.post("/panier/listes/nom")
async def renommer_liste(request: Request, reglages: ReglagesDep, nom: Annotated[str, Form()]):
    compte = service.proprietaire(request)
    active = service.cle_liste(request, reglages)
    try:
        service.enregistrer_liste(reglages, compte, nom, active)
    except ValueError:
        return RedirectResponse("/panier?erreur=nom", status_code=303)
    return RedirectResponse("/panier", status_code=303)


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
    service.ajouter(reglages, service.cle_liste(request, reglages), ajout)
    return _liste_maj(request, reglages, vider_suggestions=True)


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
    proprietaire = service.cle_liste(request, reglages)
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
    return _liste_maj(request, reglages, erreur=erreur, ticket_fini=True, vider_suggestions=True)


@router.post("/panier/lignes/mode", response_class=HTMLResponse)
async def changer_mode_liste(
    request: Request, reglages: ReglagesDep, mode: Annotated[str, Form()] = ""
):
    """Toute la liste en « le moins cher » (mode=equivalent), ou retour aux produits choisis."""
    if mode in (ModeLigne.PRODUIT, ModeLigne.EQUIVALENT):
        service.changer_mode_tout(reglages, service.cle_liste(request, reglages), ModeLigne(mode))
    return _liste_maj(request, reglages)


@router.post("/panier/lignes/{ligne_id}/mode", response_class=HTMLResponse)
async def changer_mode_ligne(
    request: Request, ligne_id: int, reglages: ReglagesDep, mode: Annotated[str, Form()] = ""
):
    """Un article : « produit précis » ↔ « le moins cher »."""
    if mode in (ModeLigne.PRODUIT, ModeLigne.EQUIVALENT):
        service.changer_mode(
            reglages, service.cle_liste(request, reglages), ligne_id, ModeLigne(mode)
        )
    return _liste_maj(request, reglages)


@router.delete("/panier/lignes/{ligne_id}", response_class=HTMLResponse)
async def supprimer_ligne(request: Request, ligne_id: int, reglages: ReglagesDep):
    proprietaire = service.cle_liste(request, reglages)
    ligne = service.lire(reglages, proprietaire, ligne_id)
    service.supprimer(reglages, proprietaire, ligne_id)
    toast = None
    if ligne:
        toast = {"message": f"« {ligne.libelle} » retiré.", "annuler": _pour_annuler([ligne])}
    return _liste_maj(request, reglages, toast=toast)


@router.post("/panier/lignes/vider", response_class=HTMLResponse)
async def vider_liste(request: Request, reglages: ReglagesDep):
    """Vide la liste d'un coup ; le message propose « Annuler »."""
    retirees = service.vider(reglages, service.cle_liste(request, reglages))
    toast = None
    if retirees:
        n = len(retirees)
        toast = {
            "message": f"Liste vidée ({n} article{'s' if n > 1 else ''}).",
            "annuler": _pour_annuler(retirees),
        }
    return _liste_maj(request, reglages, toast=toast)


@router.post("/panier/lignes/restaurer", response_class=HTMLResponse)
async def restaurer_lignes(
    request: Request, reglages: ReglagesDep, lignes: Annotated[str, Form()] = "[]"
):
    """Bouton « Annuler » : remet les articles retirés."""
    n = service.restaurer(
        reglages, service.cle_liste(request, reglages), _depuis_annulation(lignes)
    )
    toast = None
    if n:
        toast = {"message": "Article remis dans la liste." if n == 1 else f"{n} articles remis."}
    return _liste_maj(request, reglages, toast=toast)


@router.post("/panier/lignes/{ligne_id}/quantite", response_class=HTMLResponse)
async def changer_quantite(
    request: Request, ligne_id: int, reglages: ReglagesDep, quantite: Annotated[str, Form()] = ""
):
    """Boutons − et + d'un article (de 1 à 99)."""
    try:
        nombre = int(quantite)
    except ValueError:
        nombre = 0
    service.changer_quantite(reglages, service.cle_liste(request, reglages), ligne_id, nombre)
    return _liste_maj(request, reglages)


def adresse_courte(magasin: Magasin) -> str:
    ville = " ".join(magasin.ville.split())
    adresse = " ".join(magasin.adresse.split()).strip(" ,")
    rue = re.sub(r"(?:^|[,\s])\d{5}(?:\s|,|$).*$", "", adresse).rstrip(" ,")
    if ville:
        rue = re.sub(rf"(?:^|,\s*){re.escape(ville)}$", "", rue, flags=re.IGNORECASE)
    return rue


async def localisations_colonnes(magasins: list[Magasin], reglages: Reglages) -> dict[str, str]:
    villes = {m.id: " ".join(m.ville.split()) for m in magasins}
    rues = {m.id: adresse_courte(m) for m in magasins}
    proches: dict[str, str] = {}
    limite = asyncio.Semaphore(5)

    async def completer(magasin: Magasin) -> None:
        async with limite:
            ville, rue = await localisation_proche(magasin.position, reglages)
        villes[magasin.id] = villes[magasin.id] or ville
        if rue and not rues[magasin.id]:
            proches[magasin.id] = f"Près de {rue}"

    try:
        async with asyncio.timeout(2.5):
            await asyncio.gather(
                *(
                    completer(m)
                    for m in magasins
                    if not m.est_fictif and (not villes[m.id] or not rues[m.id])
                )
            )
    except TimeoutError:
        pass

    frequences = Counter(ville.casefold() for ville in villes.values() if ville)
    localisations = {}
    for magasin in magasins:
        ville = villes[magasin.id]
        if ville and frequences[ville.casefold()] == 1:
            localisations[magasin.id] = ville
            continue
        localisations[magasin.id] = (
            rues[magasin.id]
            or proches.get(magasin.id)
            or ville
            or magasin.adresse.strip()
            or magasin.code_postal.strip()
        )
    return localisations


def reperes_colonnes(magasins: list[Magasin], localisations: dict[str, str]) -> dict[str, int]:
    def cle(magasin: Magasin) -> tuple[str, str, str]:
        return (magasin.enseigne, magasin.nom.casefold(), localisations[magasin.id].casefold())

    frequences = Counter(cle(magasin) for magasin in magasins)
    numeros: Counter[tuple[str, str, str]] = Counter()
    reperes = {}
    for magasin in magasins:
        groupe = cle(magasin)
        if not localisations[magasin.id] or frequences[groupe] > 1:
            numeros[groupe] += 1
            reperes[magasin.id] = numeros[groupe]
    return reperes


@router.get("/panier/resultats", response_class=HTMLResponse)
async def tableau_resultats(request: Request, reglages: ReglagesDep):
    """Tableau vide (articles × magasins) qui se remplit ensuite par le flux SSE."""
    lignes = service.lister(reglages, service.cle_liste(request, reglages, creer=False))
    code_postal = request.session.get("code_postal", "")
    contexte: dict = {
        "lignes": lignes,
        "magasins": [],
        "message": None,
        "liste_flux": request.headers.get("X-Liste-Courses") or request.query_params.get("liste"),
    }
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
    contexte["localisations"] = await localisations_colonnes(contexte["magasins"], reglages)
    contexte["reperes"] = reperes_colonnes(contexte["magasins"], contexte["localisations"])
    return templates.TemplateResponse(request, "panier/_resultats.html", contexte)


@router.get("/panier/prix/flux", response_class=EventSourceResponse)
async def flux_prix(request: Request, reglages: ReglagesDep) -> AsyncIterable[ServerSentEvent]:
    """Une case du tableau par événement « prix-<ligne>-<magasin> », le total du magasin par
    « total-<magasin> », le classement par « resume », puis « fin » (le navigateur ferme alors).

    Ensuite, pour les drives répertoriés : chaque article sans prix y est cherché par l'extension
    (relevé récent, sinon nouvelle recherche) ; les cases et le classement se mettent à jour quand les
    prix arrivent, pendant DRIVES_ATTENTE_S secondes au plus."""
    lignes = comparables(
        service.lister(reglages, service.cle_liste(request, reglages, creer=False))
    )
    try:
        magasins = (
            await magasins_proches(
                request.session.get("code_postal", ""), reglages, request.session.get("rayon_km")
            )
        ).magasins
    except (CodePostalInvalide, CodePostalInconnu):
        magasins = []

    if lignes and magasins:
        lignes_par_id = {ligne.id: ligne for ligne in lignes}
        magasins_par_id = {magasin.id: magasin for magasin in magasins}
        resultats: dict[tuple[int, str], ResultatLigne] = {}
        async for resultat in comparer(lignes, magasins, reglages, suivre_edge=True):
            resultats[resultat.ligne_id, resultat.magasin_id] = resultat
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
                for t in calcul.totaux(lignes, magasins, resultats.values())
                if t.magasin.id == resultat.magasin_id
            )
            yield ServerSentEvent(
                event=f"total-{resultat.magasin_id}",
                raw_data=rendre("panier/_total.html", total=total),
            )
        totaux = calcul.totaux(lignes, magasins, resultats.values())
        utilisateur_id = request.session.get("utilisateur_id")
        economie = cagnotte.preparer(reglages, utilisateur_id, totaux) if utilisateur_id else None
        yield ServerSentEvent(
            event="resume",
            raw_data=rendre(
                "panier/_resume.html",
                totaux=totaux,
                economie=economie,
                prix_fictifs=any(r.prix and r.prix.est_fictif for r in resultats.values()),
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
