"""Source Open Prices (relevés de prix de la communauté Open Food Facts) : source de secours (lot 4).

Utilisée par app/collecte/repli.py quand la source d'une enseigne échoue.

- Lieu : le magasin correspond au lieu OpenStreetMap de même enseigne le plus proche, à moins de
  RAYON_LIEU_KM. Les lieux viennent de `/locations?osm_address_city__like=<ville>` et des relevés
  autour de la position (`/prices?lat=&lon=&radius_km=`). L'enseigne se lit dans `osm_brand` ou, à
  défaut, dans `osm_name` (ex. « E.Leclerc Cleunay » n'a pas de `osm_brand`).
- Prix : les relevés du lieu (`/prices?location_id=`), le plus récent par EAN, de moins de
  AGE_MAX_JOURS jours. Recherche texte : chaque mot commence un mot du nom ou de la marque.
- Les réponses sont gardées DUREE_REPONSE_MIN minutes dans le cache SQLite. Si Open Prices ne répond
  pas, ou si OPEN_PRICES_ACTIF=false, on se sert de la dernière réponse enregistrée, quel que soit son
  âge (c'est ce que remplit le préchauffage avant la démo).
- Chaque Prix porte source=TypeSource.OPEN_PRICES, le lieu et la date du relevé d'origine.
Peut aussi fournir des magasins connus d'Open Prices (ex. Intermarché sans clé, lot 2) : `trouver_magasins`.
"""

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx

from app.collecte import cache
from app.config import Reglages
from app.contrats import (
    Enseigne,
    Magasin,
    Position,
    Prix,
    Produit,
    Promotion,
    TypePromo,
    TypeSource,
)
from app.magasins.service import distance_km
from app.sources.base import SourceIndisponible, SourceNonConfiguree, SourcePrix, nouveau_client

logger = logging.getLogger(__name__)

RAYON_LIEU_KM = 2.0  # au-delà, le lieu Open Prices n'est pas considéré comme le même magasin
AGE_MAX_JOURS = 2 * 365  # relevés plus anciens ignorés (données éparses : l'année est affichée)
DUREE_REPONSE_MIN = 24 * 60  # les relevés de la communauté changent lentement
TAILLE_PAGE = 100
PAGES_MAX = 10  # 1 000 relevés par lieu au plus

# Enseigne reconnue dans « osm_brand osm_name » (texte normalisé : minuscules, sans accents).
MOTIFS_ENSEIGNE = {
    Enseigne.CARREFOUR: re.compile(r"\bcarrefour\b"),
    Enseigne.INTERMARCHE: re.compile(r"\bintermarche\b"),
    Enseigne.LECLERC: re.compile(r"\bleclerc\b"),
    Enseigne.COURSES_U: re.compile(r"\b(super u|hyper u|u express|marche u|utile)\b"),
}

_verrous: dict[tuple[int, str], asyncio.Lock] = {}


def normaliser(texte: str | None) -> str:
    sans_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", (texte or "").lower())
        if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents).split())


def enseigne_du_lieu(lieu: dict) -> Enseigne | None:
    texte = normaliser(f"{lieu.get('osm_brand') or ''} {lieu.get('osm_name') or ''}")
    for enseigne, motif in MOTIFS_ENSEIGNE.items():
        if motif.search(texte):
            return enseigne
    return None


def _distance_km(a: Position, lat: float, lon: float) -> float:
    return distance_km(a, Position(lat=lat, lon=lon))


def _moment_du_releve(releve: dict) -> datetime:
    """Date du relevé (jour du ticket ou de l'étiquette). L'heure n'est connue que si le relevé a été
    envoyé le jour même ; sinon on prend midi, heure de Paris à peu près."""
    jour = date.fromisoformat(releve["date"])
    cree = releve.get("created")
    if cree:
        moment = datetime.fromisoformat(cree.replace("Z", "+00:00"))
        if moment.date() == jour:
            return moment.astimezone(UTC)
    return datetime.combine(jour, time(11, 0), tzinfo=UTC)


def _prix_unitaire(centimes: int, produit: dict) -> tuple[int | None, str | None]:
    quantite = produit.get("product_quantity")
    unite = (produit.get("product_quantity_unit") or "").lower()
    facteurs = {
        "g": (1000, "kg"),
        "kg": (1, "kg"),
        "ml": (1000, "L"),
        "cl": (100, "L"),
        "l": (1, "L"),
    }
    if not quantite or unite not in facteurs:
        return None, None
    facteur, affichage = facteurs[unite]
    try:
        quantite_unite = float(quantite) / facteur
    except (TypeError, ValueError):
        return None, None
    if quantite_unite <= 0:
        return None, None
    return round(centimes / quantite_unite), affichage


def prix_depuis_releve(releve: dict, magasin: Magasin, lieu: dict) -> Prix | None:
    """Convertit un relevé Open Prices en Prix. None si le relevé est inexploitable."""
    ean = releve.get("product_code")
    if releve.get("type") != "PRODUCT" or not ean or releve.get("price") is None:
        return None
    if (releve.get("currency") or "EUR") != "EUR":
        return None
    produit = releve.get("product") or {}
    centimes = round(float(releve["price"]) * 100)
    if centimes <= 0:
        return None

    prix_barre = None
    promotions = []
    if releve.get("price_is_discounted") and releve.get("price_without_discount"):
        prix_barre = round(float(releve["price_without_discount"]) * 100)
        if prix_barre > centimes:
            promotions.append(
                Promotion(
                    libelle="Prix réduit",
                    type=TypePromo.IMMEDIATE,
                    remise_centimes=prix_barre - centimes,
                )
            )
        else:
            prix_barre = None
    prix_unitaire, unite = _prix_unitaire(centimes, produit)
    moment = _moment_du_releve(releve)
    ville = lieu.get("osm_address_city") or ""
    nom_lieu = lieu.get("osm_name") or "magasin"
    return Prix(
        magasin_id=magasin.id,
        produit=Produit(
            ean=ean,
            libelle=(produit.get("product_name") or "").strip() or f"Produit {ean}",
            marque=(produit.get("brands") or None),
            quantite=produit.get("quantity") or None,
        ),
        prix_centimes=centimes,
        prix_barre_centimes=prix_barre,
        prix_unitaire_centimes=prix_unitaire,
        unite=unite,
        promotions=promotions,
        source=TypeSource.OPEN_PRICES,
        source_detail=(
            f"Open Prices : {nom_lieu}{f', {ville}' if ville else ''}, relevé du {moment:%d/%m/%Y}"
        ),
        releve_le=moment,
    )


class SourceOpenPrices(SourcePrix):
    enseigne = None  # toutes enseignes
    type_source = TypeSource.OPEN_PRICES
    nom = "Open Prices (relevés de la communauté)"

    def __init__(
        self, reglages: Reglages, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.reglages = reglages
        self.transport = transport  # remplacé dans les tests (httpx.MockTransport)

    # --- Accès à l'API, avec cache ---

    async def _obtenir(self, chemin: str, parametres: dict[str, Any]) -> dict:
        cle = (
            "open_prices:"
            + chemin
            + "?"
            + "&".join(f"{k}={v}" for k, v in sorted(parametres.items()))
        )
        frais = cache.lire_reponse(self.reglages, cle, DUREE_REPONSE_MIN)
        if frais is not None:
            return frais
        if not self.reglages.open_prices_actif:
            ancien = cache.lire_reponse(self.reglages, cle, None)
            if ancien is not None:
                return ancien
            raise SourceNonConfiguree("Open Prices désactivé (OPEN_PRICES_ACTIF=false)")

        verrou = _verrous.setdefault((id(asyncio.get_running_loop()), cle), asyncio.Lock())
        async with verrou:  # une seule requête à la fois pour la même réponse
            frais = cache.lire_reponse(self.reglages, cle, DUREE_REPONSE_MIN)
            if frais is not None:
                return frais
            try:
                async with nouveau_client(
                    self.reglages.timeout_requete_s,
                    entetes={
                        "User-Agent": self.reglages.user_agent_services,
                        "Accept": "application/json",
                    },
                    transport=self.transport,
                ) as client:
                    reponse = await client.get(
                        f"{self.reglages.open_prices_url}{chemin}", params=parametres
                    )
                    reponse.raise_for_status()
                    contenu = reponse.json()
                if not isinstance(contenu, dict):
                    raise ValueError("réponse inattendue")
            except (httpx.HTTPError, ValueError) as erreur:
                ancien = cache.lire_reponse(self.reglages, cle, None)
                if ancien is not None:
                    logger.info(
                        "Open Prices injoignable, réponse enregistrée utilisée : %r", erreur
                    )
                    return ancien
                raise SourceIndisponible(f"Open Prices : {erreur!r}") from erreur
            cache.ecrire_reponse(self.reglages, cle, contenu)
            return contenu

    async def _lieux_autour(
        self, position: Position, rayon_km: float, ville: str = ""
    ) -> list[dict]:
        """Lieux Open Prices connus autour d'une position (par la ville et par les relevés proches)."""
        demandes = [
            self._obtenir(
                "/prices",
                {
                    "lat": round(position.lat, 4),
                    "lon": round(position.lon, 4),
                    "radius_km": rayon_km,
                    "size": TAILLE_PAGE,
                    "order_by": "-date",
                },
            )
        ]
        if ville:
            demandes.append(
                self._obtenir(
                    "/locations", {"osm_address_city__like": ville.strip(), "size": TAILLE_PAGE}
                )
            )
        reponses = await asyncio.gather(*demandes, return_exceptions=True)
        if all(isinstance(r, BaseException) for r in reponses):
            raise reponses[0]
        lieux: dict[int, dict] = {}
        for reponse in reponses:
            if isinstance(reponse, BaseException):
                continue
            for element in reponse.get("items", []):
                lieu = element.get("location") if "location" in element else element
                if isinstance(lieu, dict) and lieu.get("id") is not None and lieu.get("osm_lat"):
                    lieux.setdefault(lieu["id"], lieu)
        return list(lieux.values())

    async def lieu_du_magasin(self, magasin: Magasin) -> dict | None:
        """Lieu OpenStreetMap de même enseigne le plus proche du magasin, à moins de RAYON_LIEU_KM."""
        lieux = await self._lieux_autour(magasin.position, RAYON_LIEU_KM, magasin.ville)
        candidats = [
            (_distance_km(magasin.position, lieu["osm_lat"], lieu["osm_lon"]), lieu)
            for lieu in lieux
            if enseigne_du_lieu(lieu) == magasin.enseigne
        ]
        candidats = [(d, lieu) for d, lieu in candidats if d <= RAYON_LIEU_KM]
        if not candidats:
            return None
        return min(candidats, key=lambda c: (c[0], -(c[1].get("price_count") or 0)))[1]

    async def releves_du_lieu(self, lieu_id: int) -> list[dict]:
        """Relevés du lieu, du plus récent au plus ancien (pages lues en parallèle)."""
        parametres = {"location_id": lieu_id, "size": TAILLE_PAGE, "order_by": "-date"}
        premiere = await self._obtenir("/prices", {**parametres, "page": 1})
        pages = min(int(premiere.get("pages") or 1), PAGES_MAX)
        suivantes = await asyncio.gather(
            *(self._obtenir("/prices", {**parametres, "page": p}) for p in range(2, pages + 1)),
            return_exceptions=True,
        )
        releves = list(premiere.get("items", []))
        for page in suivantes:
            if not isinstance(page, BaseException):
                releves.extend(page.get("items", []))
        return releves

    async def _prix_du_magasin(self, magasin: Magasin) -> list[Prix]:
        """Le relevé le plus récent de chaque produit, pour le lieu correspondant au magasin."""
        lieu = await self.lieu_du_magasin(magasin)
        if lieu is None:
            raise SourceIndisponible(f"aucun lieu Open Prices pour {magasin.id}")
        limite = datetime.now(UTC) - timedelta(days=AGE_MAX_JOURS)
        par_ean: dict[str, Prix] = {}
        for releve in await self.releves_du_lieu(lieu["id"]):
            try:
                prix = prix_depuis_releve(releve, magasin, lieu)
            except (KeyError, TypeError, ValueError):
                continue
            if prix is None or prix.releve_le < limite:
                continue
            ancien = par_ean.get(prix.produit.ean)
            if ancien is None or prix.releve_le > ancien.releve_le:
                par_ean[prix.produit.ean] = prix
        return list(par_ean.values())

    # --- Interface SourcePrix ---

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        """Magasins des 4 enseignes connus d'Open Prices autour de la position (au plus max_magasins
        par enseigne, du plus proche au plus loin)."""
        magasins: list[Magasin] = []
        for lieu in await self._lieux_autour(position, rayon_km):
            enseigne = enseigne_du_lieu(lieu)
            if enseigne is None:
                continue
            id_enseigne = f"op-{lieu['id']}"
            magasins.append(
                Magasin(
                    id=Magasin.fabriquer_id(enseigne, id_enseigne),
                    enseigne=enseigne,
                    id_enseigne=id_enseigne,
                    nom=lieu.get("osm_name") or enseigne.nom,
                    code_postal=lieu.get("osm_address_postcode") or "",
                    ville=lieu.get("osm_address_city") or "",
                    position=Position(lat=lieu["osm_lat"], lon=lieu["osm_lon"]),
                    distance_km=round(_distance_km(position, lieu["osm_lat"], lieu["osm_lon"]), 1),
                )
            )
        magasins.sort(key=lambda m: m.distance_km)
        par_enseigne: dict[Enseigne, int] = {}
        retenus = []
        for magasin in magasins:
            if par_enseigne.get(magasin.enseigne, 0) < max_magasins:
                par_enseigne[magasin.enseigne] = par_enseigne.get(magasin.enseigne, 0) + 1
                retenus.append(magasin)
        return retenus

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        # Mots utiles, au singulier approximatif (« pâtes » trouve « Pâte »).
        mots = [
            m[:-1] if len(m) > 3 and m[-1] in "sx" else m for m in normaliser(recherche).split()
        ]
        mots = [m for m in mots if len(m) >= 2]
        if not mots:
            return []
        trouves = []
        for prix in await self._prix_du_magasin(magasin):
            mots_produit = normaliser(f"{prix.produit.libelle} {prix.produit.marque or ''}").split()
            if all(any(m.startswith(mot) for m in mots_produit) for mot in mots):
                trouves.append(prix)
        return sorted(trouves, key=lambda p: p.prix_centimes)[:limite]

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        for prix in await self._prix_du_magasin(magasin):
            if prix.produit.ean == ean:
                return prix
        return None
