"""Recherche d'articles pour composer la liste (référentiel produits, lot 4).

- SOURCE_PRODUITS=open_food_facts (défaut) : recherche texte sur search.openfoodfacts.org
  (search-a-licious ; la recherche classique `cgi/search.pl` renvoie souvent 503).
- Recherche pendant la frappe : le dernier mot est un début de mot (« spag » → `spag*`), les autres doivent
  tous être présents ; candidats triés par popularité, complétés par la recherche classique s'il en manque.
- Les résultats sont reclassés sur place : d'abord ceux dont le nom ou la marque contient tous les mots (le
  dernier en début de mot), puis ceux qui ont la quantité demandée, puis le nom le plus simple (qui commence
  par la recherche, avec le moins de mots en plus ; un EAN français, préfixe 3, compte pour deux mots de
  moins), puis les plus scannés.
- Quantité dans la recherche (« nutella 400 g », « lait 1 L », « coca 6 x 1,5 L ») : elle est retirée des mots
  cherchés (sinon Open Food Facts ne renvoie rien) et sert à une recherche ciblée sur le champ `quantity`,
  complétée par la recherche générale. 1 kg = 1000 g, 1 L = 100 cl = 1000 ml.
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
    """Minuscules, sans accents ni ponctuation ; « œ » et « æ » deviennent « oe » et « ae »."""
    texte = (texte or "").lower().replace("œ", "oe").replace("æ", "ae")
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents).split())


# Quantité : « 400 g », « 1,5 L », « 6 x 1 L », « 6*25 cl »… Unités ramenées au gramme ou au millilitre.
UNITES = {
    "mg": (0.001, "g"),
    "g": (1, "g"),
    "gr": (1, "g"),
    "gramme": (1, "g"),
    "grammes": (1, "g"),
    "kg": (1000, "g"),
    "kilo": (1000, "g"),
    "kilos": (1000, "g"),
    "ml": (1, "ml"),
    "cl": (10, "ml"),
    "dl": (100, "ml"),
    "l": (1000, "ml"),
    "lt": (1000, "ml"),
    "lts": (1000, "ml"),
    "litre": (1000, "ml"),
    "litres": (1000, "ml"),
}
MOTIF_QUANTITE = re.compile(
    r"(?:(\d+)\s*[x×*]\s*)?(\d+(?:[.,]\d+)?)\s*("
    + "|".join(sorted(UNITES, key=len, reverse=True))
    + r")(?![a-z])",
    re.IGNORECASE,
)


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte.lower()) if not unicodedata.combining(c)
    )


def lire_quantite(texte: str | None) -> tuple[float, str] | None:
    """Quantité totale en grammes ou millilitres : « 6 x 1 L » → (6000, "ml"), « 400 g e » → (400, "g")."""
    trouve = MOTIF_QUANTITE.search(_sans_accents(texte or ""))
    if trouve is None:
        return None
    nombre = int(trouve[1]) if trouve[1] else 1
    valeur = float(trouve[2].replace(",", "."))
    facteur, unite = UNITES[trouve[3].lower()]
    return nombre * valeur * facteur, unite


def separer_quantite(texte: str) -> tuple[str, tuple[float, str] | None]:
    """(« nutella », (400, "g")) pour « nutella 400 g ». Texte inchangé s'il n'y a pas de quantité."""
    sans_accents = _sans_accents(texte)
    trouve = MOTIF_QUANTITE.search(sans_accents)
    if trouve is None:
        return texte, None
    reste = " ".join((texte[: trouve.start()] + " " + texte[trouve.end() :]).split())
    return reste, lire_quantite(sans_accents)


def meme_quantite(a: tuple[float, str] | None, b: tuple[float, str] | None) -> bool:
    return a is not None and b is not None and a[1] == b[1] and abs(a[0] - b[0]) <= 0.01 * a[0]


def _nombre(valeur: float) -> str:
    return str(int(valeur)) if valeur == int(valeur) else f"{valeur:g}"


def requete_ciblee(texte: str, quantite: tuple[float, str]) -> str:
    """« (nutella) AND quantity:(400*) » ; plusieurs écritures pour 1 kg (1*, 1000*) ou 1 L (1*, 100*, 1000*)."""
    valeur, unite = quantite
    ecritures = {_nombre(valeur)}
    if valeur >= 1000:
        ecritures.add(_nombre(valeur / 1000))  # kg ou L
    if unite == "ml" and valeur >= 10:
        ecritures.add(_nombre(valeur / 10))  # cl
    ecritures |= {
        e.replace(".", ",") for e in ecritures if "." in e
    }  # « 1,5 L » s'écrit aussi « 1.5 L »
    return f"({texte}) AND quantity:({' OR '.join(sorted(e + '*' for e in ecritures))})"


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


def requete_prefixe(texte: str) -> str | None:
    """« spag » → « spag* », « pain de mi » → « pain AND de AND mi* » (recherche pendant la frappe)."""
    mots = re.findall(r"[^\W_]+", texte.lower())
    if not mots or len(mots[-1]) < 2:
        return None
    return " AND ".join([*mots[:-1], mots[-1] + "*"])


def _mots_produit(hit: dict) -> list[str]:
    libelle = hit.get("product_name_fr") or hit.get("product_name") or ""
    return normaliser(f"{libelle} {' '.join(hit.get('brands') or [])}").split()


def correspond(hit: dict, mots: list[str]) -> bool:
    """Chaque mot de la recherche commence un mot du nom ou de la marque (« spag » → « Spaghetti »)."""
    mots_produit = _mots_produit(hit)
    return all(any(m.startswith(mot) for m in mots_produit) for mot in mots)


def produits_depuis_reponse(contenu: dict, texte: str) -> list[Produit]:
    """Produits d'une réponse search-a-licious, reclassés pour la recherche `texte`."""
    texte, quantite_voulue = separer_quantite(texte)
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
        mots_nom = normaliser(libelle).split()
        en_plus = max(len(mots_nom) - len(mots), 0)
        commence = bool(mots and mots_nom and mots_nom[0].startswith(mots[0]))
        cle = (
            not correspond(hit, mots),
            not meme_quantite(quantite_voulue, lire_quantite(produit.quantite)),
            # Nom le plus simple d'abord : « Spaghetti 500 g » avant « Sauce à spag ».
            (0 if commence else 2) + en_plus - (2 if ean.startswith("3") else 0),
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
    texte: str,
    reglages: Reglages,
    transport: httpx.AsyncBaseTransport | None,
    tri: str | None = None,
) -> dict | None:
    cle = f"off:recherche:{normaliser(texte)}" + (f":{tri}" if tri else "")
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
                    params={
                        "q": texte,
                        "page_size": TAILLE_PAGE,
                        "langs": "fr",
                        "fields": CHAMPS,
                        **({"sort_by": tri} if tri else {}),
                    },
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

    base, quantite = separer_quantite(texte)
    hits: list[dict] = []
    if quantite is not None and len(base) >= 2:
        # Recherche ciblée sur la quantité d'abord ; la recherche générale complète si besoin.
        ciblee = await _reponse_off(requete_ciblee(base, quantite), reglages, transport)
        hits += (ciblee or {}).get("hits") or []
    recherche = base if len(base) >= 2 else texte
    mots = mots_recherche(recherche)
    if (prefixe := requete_prefixe(recherche)) is not None:
        # Pendant la frappe : dernier mot en début de mot, candidats les plus scannés d'abord.
        populaires = await _reponse_off(prefixe, reglages, transport, tri="-unique_scans_n")
        hits += (populaires or {}).get("hits") or []
    if sum(correspond(hit, mots) for hit in hits) < limite:
        generale = await _reponse_off(recherche, reglages, transport)
        hits += (generale or {}).get("hits") or []
    produits = produits_depuis_reponse({"hits": hits}, texte)[:limite]
    if not produits:
        return _catalogue_fictif(base if len(base) >= 2 else texte, limite)
    enregistrer(reglages, produits)
    return produits
