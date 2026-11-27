"""Recherche d'articles pour composer la liste (référentiel produits, lot 4).

- SOURCE_PRODUITS=open_food_facts (défaut) : recherche texte sur search.openfoodfacts.org
  (search-a-licious ; la recherche classique `cgi/search.pl` renvoie souvent 503).
- Les résultats sont reclassés sur place : d'abord ceux dont le nom ou la marque contient tous les
  mots, les EAN français (préfixe 3) en tête, puis les plus scannés.
- Appels espacés d'au moins INTERVALLE_MIN_S secondes, réponses gardées DUREE_REPONSE_MIN minutes
  dans le cache SQLite (et réutilisées, même anciennes, si le service ne répond plus).
- Si Open Food Facts ne donne rien (panne, 503, délai), on cherche dans le catalogue fictif.
- SOURCE_PRODUITS=fictive : catalogue fictif seulement, aucun appel réseau (tests).
Les produits trouvés sont enregistrés dans la table `produit` (`produit_par_ean`).
"""

import asyncio
import logging
import re
import sqlite3
import time
import unicodedata
from datetime import UTC, datetime

import httpx

from app import db
from app.collecte import cache
from app.config import Reglages
from app.contrats import Produit
from app.sources.base import nouveau_client
from app.sources.fictive import rechercher_catalogue

logger = logging.getLogger(__name__)

INTERVALLE_MIN_S = (
    1.0  # entre deux appels à Open Food Facts (503 au-delà d'une dizaine d'appels rapprochés)
)
DUREE_REPONSE_MIN = 7 * 24 * 60
TAILLE_PAGE = 50
CHAMPS = "code,product_name_fr,product_name,brands,quantity,unique_scans_n"

_verrou: asyncio.Lock | None = None
_verrou_boucle: asyncio.AbstractEventLoop | None = None
_dernier_appel = 0.0


def normaliser(texte: str | None) -> str:
    sans_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", (texte or "").lower())
        if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents).split())


def mots_recherche(texte: str) -> list[str]:
    """Mots utiles, au singulier approximatif (« oeufs » trouve « Oeuf »)."""
    mots = []
    for mot in normaliser(texte).split():
        if len(mot) < 2:
            continue
        if len(mot) > 3 and mot[-1] in "sx":
            mot = mot[:-1]
        mots.append(mot)
    return mots


def _marque(marques: list[str] | str | None) -> str | None:
    if not marques:
        return None
    premiere = marques[0] if isinstance(marques, list) else marques.split(",")[0]
    premiere = re.sub(r"^[a-z]{2}:", "", premiere).strip()
    if not premiere:
        return None
    return premiere[0].upper() + premiere[1:] if premiere.islower() else premiere


def produits_depuis_reponse(contenu: dict, texte: str) -> list[Produit]:
    """Produits d'une réponse search-a-licious, reclassés pour la recherche `texte`."""
    mots = mots_recherche(texte)
    candidats = []
    vus: set[str] = set()
    for rang, hit in enumerate(contenu.get("hits") or []):
        ean = str(hit.get("code") or "").strip()
        libelle = (hit.get("product_name_fr") or hit.get("product_name") or "").strip()
        if not re.fullmatch(r"\d{8,14}", ean) or not libelle or ean in vus:
            continue
        vus.add(ean)
        produit = Produit(
            ean=ean,
            libelle=libelle,
            marque=_marque(hit.get("brands")),
            quantite=(hit.get("quantity") or "").strip() or None,
        )
        texte_produit = normaliser(f"{libelle} {' '.join(hit.get('brands') or [])}")
        correspond = all(mot in texte_produit for mot in mots)
        cle = (
            not correspond,
            not ean.startswith("3"),
            produit.quantite is None,
            -(hit.get("unique_scans_n") or 0),
            rang,
        )
        candidats.append((cle, produit))
    candidats.sort(key=lambda c: c[0])
    return [produit for _, produit in candidats]


async def _patienter() -> None:
    """Espace les appels à Open Food Facts (un appel à la fois, INTERVALLE_MIN_S entre deux)."""
    global _dernier_appel
    attente = _dernier_appel + INTERVALLE_MIN_S - time.monotonic()
    if attente > 0:
        await asyncio.sleep(attente)
    _dernier_appel = time.monotonic()


def _verrou_courant() -> asyncio.Lock:
    global _verrou, _verrou_boucle
    boucle = asyncio.get_running_loop()
    if _verrou is None or _verrou_boucle is not boucle:
        _verrou, _verrou_boucle = asyncio.Lock(), boucle
    return _verrou


async def _reponse_off(
    texte: str, reglages: Reglages, transport: httpx.AsyncBaseTransport | None
) -> dict | None:
    cle = f"off:recherche:{normaliser(texte)}"
    frais = cache.lire_reponse(reglages, cle, DUREE_REPONSE_MIN)
    if frais is not None:
        return frais
    async with _verrou_courant():
        frais = cache.lire_reponse(reglages, cle, DUREE_REPONSE_MIN)
        if frais is not None:
            return frais
        await _patienter()
        try:
            async with nouveau_client(
                reglages.timeout_requete_s,
                entetes={"User-Agent": reglages.user_agent_services, "Accept": "application/json"},
                transport=transport,
            ) as client:
                reponse = await client.get(
                    f"{reglages.open_food_facts_recherche_url}/search",
                    params={"q": texte, "page_size": TAILLE_PAGE, "langs": "fr", "fields": CHAMPS},
                )
                reponse.raise_for_status()
                contenu = reponse.json()
            if not isinstance(contenu, dict) or "hits" not in contenu:
                raise ValueError("réponse inattendue")
        except (httpx.HTTPError, ValueError) as erreur:
            logger.info("Open Food Facts ne répond pas pour « %s » : %r", texte, erreur)
            return cache.lire_reponse(reglages, cle, None)
    cache.ecrire_reponse(reglages, cle, contenu)
    return contenu


def enregistrer(reglages: Reglages, produits: list[Produit]) -> None:
    maintenant = datetime.now(UTC).isoformat()
    try:
        with db.connexion(reglages.db_path) as cnx:
            cnx.executemany(
                "INSERT OR REPLACE INTO produit (ean, libelle, marque, quantite, source, maj_le) "
                "VALUES (?, ?, ?, ?, 'open_food_facts', ?)",
                [(p.ean, p.libelle, p.marque, p.quantite, maintenant) for p in produits if p.ean],
            )
    except sqlite3.Error:
        logger.exception("Enregistrement des produits impossible")


def produit_par_ean(reglages: Reglages, ean: str) -> Produit | None:
    try:
        with db.connexion(reglages.db_path) as cnx:
            ligne = cnx.execute(
                "SELECT ean, libelle, marque, quantite FROM produit WHERE ean = ?", (ean,)
            ).fetchone()
    except sqlite3.Error:
        return None
    return Produit(**dict(ligne)) if ligne else None


def _catalogue_fictif(texte: str, limite: int) -> list[Produit]:
    return [article.produit() for article in rechercher_catalogue(texte)[:limite]]


async def rechercher(
    texte: str,
    reglages: Reglages,
    limite: int = 8,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[Produit]:
    texte = " ".join(texte.split())[:120]
    if len(texte) < 2:
        return []
    if reglages.source_produits.strip().lower() == "fictive":
        return _catalogue_fictif(texte, limite)

    contenu = await _reponse_off(texte, reglages, transport)
    produits = produits_depuis_reponse(contenu, texte)[:limite] if contenu else []
    if not produits:
        return _catalogue_fictif(texte, limite)
    enregistrer(reglages, produits)
    return produits
