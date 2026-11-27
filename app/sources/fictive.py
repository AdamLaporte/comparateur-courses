"""Source de données FICTIVES, pour le développement, les tests et la démo de secours.

Tout ce qu'elle produit est marqué `est_fictif=True` et affiché « Données fictives ».
Les prix sont stables d'un lancement à l'autre (calculés à partir d'une empreinte) et varient
selon l'enseigne et le magasin. Quelques produits manquent dans certains magasins, et certains
ont une promotion (immédiate, « le 2e à -50 % » ou fidélité).

Les cinq premiers articles du catalogue ont de vrais EAN (Open Food Facts, Carrefour) ; les autres
ont des EAN fictifs commençant par 2 (plage réservée à l'usage interne) et des marques inventées.
"""

import asyncio
import hashlib
import math
import random
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

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
from app.sources.base import SourcePrix

LIBELLE_SOURCE = "Données fictives"


@dataclass(frozen=True)
class ArticleFictif:
    ean: str
    libelle: str
    marque: str
    quantite: str
    prix_base: int  # centimes
    mots_cles: str = ""
    contenance: float | None = None  # dans l'unité ci-dessous, pour le prix au kilo ou au litre
    unite: str | None = None
    exclusif: Enseigne | None = None  # marque distributeur : vendue dans une seule enseigne

    def produit(self) -> Produit:
        return Produit(
            ean=self.ean, libelle=self.libelle, marque=self.marque, quantite=self.quantite
        )


_CATALOGUE_BASE = [
    # Vrais EAN.
    ArticleFictif(
        "3017620422003",
        "Pâte à tartiner aux noisettes et au cacao",
        "Nutella",
        "400 g",
        359,
        "pate a tartiner chocolat noisette",
        0.4,
        "kg",
    ),
    ArticleFictif(
        "5449000214911",
        "Coca-Cola Original (canette)",
        "Coca-Cola",
        "330 ml",
        95,
        "soda cola boisson",
        0.33,
        "L",
    ),
    ArticleFictif(
        "3487400005526",
        "Riz cuisiné tomate et huile d'olive",
        "Uncle Ben's",
        "250 g",
        249,
        "riz",
        0.25,
        "kg",
    ),
    ArticleFictif(
        "8000070200289",
        "Café torréfié moulu",
        "Carte Noire",
        "250 g",
        469,
        "cafe moulu",
        0.25,
        "kg",
    ),
    ArticleFictif(
        "3276554163158",
        "Lait demi-écrémé",
        "Carrefour Classic'",
        "1 L",
        105,
        "lait demi ecreme",
        1.0,
        "L",
        Enseigne.CARREFOUR,
    ),
    # EAN et marques fictifs.
    ArticleFictif(
        "2000000000011",
        "Lait demi-écrémé UHT",
        "Laiterie du Bocage (fictif)",
        "1 L",
        119,
        "lait demi ecreme",
        1.0,
        "L",
    ),
    ArticleFictif(
        "2000000000028",
        "Spaghetti n°5",
        "Pastissimo (fictif)",
        "500 g",
        135,
        "pates spaghetti",
        0.5,
        "kg",
    ),
    ArticleFictif(
        "2000000000035",
        "Penne rigate",
        "Pastissimo (fictif)",
        "500 g",
        135,
        "pates penne",
        0.5,
        "kg",
    ),
    ArticleFictif(
        "2000000000042", "Riz long grain", "Rizière d'Or (fictif)", "1 kg", 229, "riz", 1.0, "kg"
    ),
    ArticleFictif(
        "2000000000059",
        "Œufs de poules élevées en plein air x12",
        "Ferme des Prés (fictif)",
        "12 œufs",
        389,
        "oeufs",
    ),
    ArticleFictif(
        "2000000000066",
        "Beurre doux",
        "Laiterie du Bocage (fictif)",
        "250 g",
        279,
        "beurre",
        0.25,
        "kg",
    ),
    ArticleFictif(
        "2000000000073",
        "Yaourts nature x8",
        "Laiterie du Bocage (fictif)",
        "8 x 125 g",
        189,
        "yaourt nature",
        1.0,
        "kg",
    ),
    ArticleFictif(
        "2000000000080",
        "Pain de mie complet",
        "Bonjour Matin (fictif)",
        "500 g",
        219,
        "pain de mie",
        0.5,
        "kg",
    ),
    ArticleFictif(
        "2000000000097",
        "Emmental râpé",
        "Fromagerie Comtoise (fictif)",
        "200 g",
        239,
        "fromage rape emmental",
        0.2,
        "kg",
    ),
    ArticleFictif(
        "2000000000103",
        "Sauce tomate au basilic",
        "Pastissimo (fictif)",
        "400 g",
        189,
        "sauce tomate",
        0.4,
        "kg",
    ),
    ArticleFictif(
        "2000000000110",
        "Bananes",
        "Vergers du Sud (fictif)",
        "1 kg",
        199,
        "banane fruit",
        1.0,
        "kg",
    ),
    ArticleFictif(
        "2000000000127",
        "Papier toilette x12",
        "Douceur (fictif)",
        "12 rouleaux",
        449,
        "papier toilette",
    ),
]

# Marques distributeur fictives : une par enseigne, moins chères (utile pour le mode « équivalent »).
_MDD = [
    (
        "100",
        "Pâte à tartiner noisettes cacao",
        "400 g",
        205,
        "pate a tartiner chocolat noisette",
        0.4,
        "kg",
    ),
    ("101", "Spaghetti", "500 g", 79, "pates spaghetti", 0.5, "kg"),
    ("102", "Lait demi-écrémé", "1 L", 97, "lait demi ecreme", 1.0, "L"),
]
_NUMEROS_ENSEIGNE = {
    Enseigne.CARREFOUR: "1",
    Enseigne.INTERMARCHE: "2",
    Enseigne.COURSES_U: "3",
    Enseigne.LECLERC: "4",
}

CATALOGUE: list[ArticleFictif] = _CATALOGUE_BASE + [
    ArticleFictif(
        f"2000000{code}{num}00",
        libelle,
        f"Marque distributeur {enseigne.nom} (fictif)",
        quantite,
        prix,
        mots,
        contenance,
        unite,
        enseigne,
    )
    for enseigne, num in _NUMEROS_ENSEIGNE.items()
    for code, libelle, quantite, prix, mots, contenance, unite in _MDD
    # Carrefour a déjà son vrai lait demi-écrémé dans le catalogue.
    if not (enseigne == Enseigne.CARREFOUR and code == "102")
]
CATALOGUE_PAR_EAN = {a.ean: a for a in CATALOGUE}

_FACTEURS_ENSEIGNE = {
    Enseigne.LECLERC: 0.95,
    Enseigne.INTERMARCHE: 0.98,
    Enseigne.COURSES_U: 1.00,
    Enseigne.CARREFOUR: 1.03,
}
_NOMS_MAGASINS = {
    Enseigne.CARREFOUR: ["Carrefour Market", "Carrefour Drive", "Carrefour City"],
    Enseigne.INTERMARCHE: ["Intermarché Super", "Intermarché Hyper", "Intermarché Express"],
    Enseigne.COURSES_U: ["Super U", "Hyper U", "U Express"],
    Enseigne.LECLERC: ["E.Leclerc Drive", "E.Leclerc Relais Drive", "E.Leclerc Drive piéton"],
}


def empreinte(*parties: object) -> int:
    """Entier stable (contrairement à hash(), qui change à chaque lancement de Python)."""
    texte = "|".join(str(p) for p in parties)
    return int(hashlib.sha256(texte.encode("utf-8")).hexdigest()[:12], 16)


def normaliser(texte: str) -> str:
    """Minuscules sans accents, pour comparer des recherches."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().replace("'", " ").split())


def rechercher_catalogue(recherche: str) -> list[ArticleFictif]:
    """Articles du catalogue dont le texte contient tous les mots de la recherche."""
    mots = [m for m in normaliser(recherche).split() if len(m) >= 2]
    if not mots:
        return []
    resultats = []
    for article in CATALOGUE:
        texte = normaliser(f"{article.libelle} {article.marque} {article.mots_cles} {article.ean}")
        if all(mot in texte for mot in mots):
            resultats.append(article)
    return resultats


class SourceFictive(SourcePrix):
    type_source = TypeSource.FICTIVE
    nom = LIBELLE_SOURCE

    def __init__(self, enseigne: Enseigne, delai_max_s: float = 0.0) -> None:
        self.enseigne = enseigne
        self.delai_max_s = delai_max_s

    async def _patienter(self) -> None:
        if self.delai_max_s > 0:
            await asyncio.sleep(random.uniform(0, self.delai_max_s))

    async def trouver_magasins(
        self, position: Position, rayon_km: float, max_magasins: int
    ) -> list[Magasin]:
        await self._patienter()
        magasins = []
        for i, nom in enumerate(_NOMS_MAGASINS[self.enseigne], start=1):
            h = empreinte(round(position.lat, 2), round(position.lon, 2), self.enseigne, i)
            distance_km = 0.8 + (h % 800) / 100  # entre 0,8 et 8,8 km
            angle = math.radians((h // 1000) % 360)
            lat = position.lat + distance_km / 111.0 * math.cos(angle)
            lon = position.lon + distance_km / (111.0 * math.cos(math.radians(position.lat))) * (
                math.sin(angle)
            )
            id_enseigne = f"fictif-{h % 100000}"
            magasins.append(
                Magasin(
                    id=Magasin.fabriquer_id(self.enseigne, id_enseigne),
                    enseigne=self.enseigne,
                    id_enseigne=id_enseigne,
                    nom=f"{nom} (fictif)",
                    adresse=f"{1 + h % 90} rue imaginaire",
                    position=Position(lat=lat, lon=lon),
                    est_fictif=True,
                )
            )
        return magasins

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        await self._patienter()
        offres = [
            prix
            for article in rechercher_catalogue(recherche)
            if (prix := self._prix_article(magasin, article)) is not None
        ]
        return sorted(offres, key=lambda p: p.prix_centimes)[:limite]

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        await self._patienter()
        article = CATALOGUE_PAR_EAN.get(ean)
        if article is None:
            # EAN hors catalogue (ex. produit venu d'Open Food Facts) : prix fictif générique.
            article = ArticleFictif(
                ean, f"Article {ean}", "Marque inconnue (fictif)", "", 150 + empreinte(ean) % 500
            )
        return self._prix_article(magasin, article)

    def _prix_article(self, magasin: Magasin, article: ArticleFictif) -> Prix | None:
        if article.exclusif is not None and article.exclusif != self.enseigne:
            return None
        h = empreinte(magasin.id, article.ean)
        if h % 11 == 0:  # environ 9 % des produits manquent dans un magasin donné
            return None

        facteur = 1.0 if article.exclusif else _FACTEURS_ENSEIGNE[self.enseigne]
        variation = ((h // 11) % 13 - 6) / 100  # de -6 % à +6 %
        prix = max(10, round(article.prix_base * facteur * (1 + variation)))
        prix_barre = None
        promotions: list[Promotion] = []

        match (h // 1000) % 9:
            case 1:
                prix_barre, prix = prix, round(prix * 0.8)
                promotions.append(
                    Promotion(
                        libelle="-20 % immédiat",
                        type=TypePromo.IMMEDIATE,
                        remise_centimes=prix_barre - prix,
                    )
                )
            case 2:
                promotions.append(
                    Promotion(
                        libelle="Le 2e à -50 %",
                        type=TypePromo.LOT,
                        remise_centimes=prix // 2,
                        quantite_min=2,
                    )
                )
            case 3:
                promotions.append(
                    Promotion(
                        libelle="-10 % avec la carte de fidélité",
                        type=TypePromo.FIDELITE,
                        remise_centimes=round(prix * 0.1),
                    )
                )

        prix_unitaire = round(prix / article.contenance) if article.contenance else None
        return Prix(
            magasin_id=magasin.id,
            produit=article.produit(),
            prix_centimes=prix,
            prix_barre_centimes=prix_barre,
            prix_unitaire_centimes=prix_unitaire,
            unite=article.unite,
            promotions=promotions,
            source=TypeSource.FICTIVE,
            source_detail=LIBELLE_SOURCE,
            releve_le=datetime.now(UTC),
            est_fictif=True,
        )
