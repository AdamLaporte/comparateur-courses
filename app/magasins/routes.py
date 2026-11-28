"""Routes : accueil (ville, code postal ou position, et rayon) et magasins proches (page HTML et JSON)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.comptes import lieux
from app.config import ReglagesDep
from app.contrats import Enseigne, MagasinsReponse, Position
from app.gabarits import templates
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide, adresse_proche
from app.magasins.service import magasins_proches
from app.magasins.trajets import MODES, estimer
from app.mode_donnees import est_reel
from app.panier import service as panier

router = APIRouter(tags=["magasins"])

MESSAGE_INVALIDE = "Saisis une ville ou un code postal à 5 chiffres, par exemple Bruz ou 35170."
MESSAGE_INCONNU = "Ce lieu est introuvable pour l'instant. Vérifie-le ou réessaie."
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
    return len(panier.lister(reglages, panier.cle_liste(request, reglages, creer=False)))


def contexte_trajet(request: Request, reglages) -> dict:
    favoris = {
        str(lieu["id"]): lieu
        for lieu in lieux.lister(reglages, request.session.get("utilisateur_id"))
    }
    maison = request.session.get("maison")
    defaut = next(
        (
            identifiant
            for identifiant, lieu in favoris.items()
            if lieu["nom"].casefold() == "maison"
        ),
        "",
    )
    if maison and not defaut:
        favoris["maison"] = {
            "nom": "Maison",
            "adresse": maison["code_postal"],
            "detail": f"{maison['code_postal']} {maison['ville']}",
            "mode": "voiture",
        }
        defaut = "maison"
    return {
        "lieux_trajet": favoris,
        "lieu_defaut": defaut,
        "modes_trajet": MODES,
    }


@router.get("/", response_class=HTMLResponse)
async def accueil(request: Request, reglages: ReglagesDep):
    contexte = contexte_trajet(request, reglages)
    actif = request.session.get("lieu_trajet")
    if actif in contexte["lieux_trajet"]:
        contexte["lieu_trajet"] = actif
    return templates.TemplateResponse(
        request,
        "magasins/accueil.html",
        {
            "code_postal": request.session.get("code_postal", ""),
            "ville_recherche": request.session.get("ville_recherche", ""),
            "rayon_km": request.session.get("rayon_km"),
            "rayons": RAYONS_KM,
            "nb_articles": nb_articles(request, reglages),
            **contexte,
        },
    )


@router.get("/magasins", response_class=HTMLResponse)
async def page_magasins(
    request: Request,
    reglages: ReglagesDep,
    code_postal: str = "",
    rayon_km: str = "",
    lieu_trajet: str = "",
    trajet: bool = False,
    mode_trajet: str = "",
    rayon_trajet: str = "",
    enseigne: Enseigne | None = None,
):
    contexte = contexte_trajet(request, reglages)
    contexte["mode_reel"] = est_reel(request)
    favori = contexte["lieux_trajet"].get(lieu_trajet)
    lieu_enregistre = None
    if favori:
        code_postal = favori["adresse"]
        if "lat" in favori:
            position = Position(lat=favori["lat"], lon=favori["lon"])
            code_postal = f"{position.lat:.7f},{position.lon:.7f}"
            lieu_enregistre = (favori["nom"], position)
    identifiant_mode = (
        mode_trajet if mode_trajet in MODES else (favori or {}).get("mode", "voiture")
    )
    mode = MODES[identifiant_mode] if trajet else None
    rayon = (lire_rayon(rayon_trajet) or mode.rayon) if mode else lire_rayon(rayon_km)
    contexte.update(
        lieu_trajet=lieu_trajet if favori else "",
        trajet_actif=trajet,
        mode_trajet=mode_trajet if mode else "",
        rayon_trajet=rayon_trajet,
    )
    try:
        reponse = await magasins_proches(
            code_postal,
            reglages,
            rayon,
            lieu_enregistre=lieu_enregistre,
            seulement_drives=contexte["mode_reel"],
        )
    except (CodePostalInvalide, CodePostalInconnu) as erreur:
        message = MESSAGE_INVALIDE if isinstance(erreur, CodePostalInvalide) else MESSAGE_INCONNU
        contexte.update(
            {
                "code_postal": code_postal,
                "rayon_km": rayon,
                "rayons": RAYONS_KM,
                "erreur": message,
            }
        )
        return templates.TemplateResponse(request, "magasins/accueil.html", contexte)
    request.session["code_postal"] = reponse.code_postal
    request.session["ville_recherche"] = reponse.ville if not favori else ""
    request.session["rayon_km"] = rayon
    if favori:
        reponse.ville = favori["nom"]
        request.session["lieu_trajet"] = lieu_trajet
    else:
        request.session.pop("lieu_trajet", None)
    if mode:
        contexte["estimations_trajet"] = {
            magasin.id: estimer(reponse.position, magasin.position, mode, rayon)
            for magasin in reponse.magasins
        }
        contexte["nom_mode"] = mode.nom
    enseignes = list(dict.fromkeys(m.enseigne for m in reponse.magasins))
    magasins_affiches = [m for m in reponse.magasins if enseigne is None or m.enseigne == enseigne]
    return templates.TemplateResponse(
        request,
        "magasins/liste.html",
        {
            "reponse": reponse,
            "magasins_affiches": magasins_affiches,
            "enseignes_filtres": enseignes,
            "enseigne_active": enseigne,
            "nb_articles": nb_articles(request, reglages),
            **contexte,
        },
    )


@router.get("/api/magasins", response_model=MagasinsReponse)
async def api_magasins(code_postal: str, reglages: ReglagesDep, rayon_km: float | None = None):
    try:
        return await magasins_proches(code_postal, reglages, lire_rayon(rayon_km))
    except CodePostalInvalide as erreur:
        raise HTTPException(422, MESSAGE_INVALIDE) from erreur
    except CodePostalInconnu as erreur:
        raise HTTPException(404, MESSAGE_INCONNU) from erreur


@router.get("/api/adresse-proche")
async def api_adresse_proche(lat: float, lon: float, reglages: ReglagesDep):
    """Bouton « Me localiser » : l'adresse la plus proche de la position du navigateur, pour l'afficher
    dans le champ à la place des coordonnées. 404 si aucune adresse n'est trouvée."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "Position invalide.")
    adresse = await adresse_proche(Position(lat=lat, lon=lon), reglages)
    if not adresse:
        raise HTTPException(404, "Aucune adresse trouvée près de cette position.")
    return {"adresse": adresse}
