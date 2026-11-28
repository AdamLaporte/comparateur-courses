"""Source de données FICTIVES, pour le développement, les tests et la démo de secours.

Tout ce qu'elle produit est marqué `est_fictif=True` et `source=TypeSource.FICTIVE` : ce marquage interne
empêche le fictif d'entrer dans le cache, de se mêler aux prix réels ou de partir vers Open Prices.
À l'écran, en mode démo, rien ne le distingue d'un relevé réel (libellé neutre, marques sans mention) :
décision du 28/11, voir docs/decisions.md.
Les prix sont stables d'un lancement à l'autre (calculés à partir d'une empreinte) et varient
selon l'enseigne et le magasin ; certains ont une promotion (immédiate, « le 2e à -50 % » ou fidélité).
Chaque article a un prix dans chaque magasin : une recherche ou un EAN hors catalogue reçoit un article
générique. Les marques distributeur ne sortent des recherches que dans leur enseigne.

Les cinq premiers articles du catalogue ont de vrais EAN (Open Food Facts, Carrefour) ; les autres
ont des EAN fictifs commençant par 2 (plage réservée à l'usage interne) et des marques inventées.
"""

import asyncio
import hashlib
import math
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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

LIBELLE_SOURCE = "Données fictives"  # nom interne de la source (journaux), jamais affiché
LIBELLE_AFFICHE = "Relevé en magasin"  # source_detail (API) ; l'écran n'affiche que la date
# Seules les premières requêtes attendent (affichage progressif) : une longue liste ne dépasse jamais
# le temps laissé à une enseigne.
REQUETES_RETARDEES = 12


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
            ean=self.ean,
            libelle=self.libelle,
            marque=self.marque or None,
            quantite=self.quantite or None,
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
        "Laiterie du Bocage",
        "1 L",
        119,
        "lait demi ecreme",
        1.0,
        "L",
    ),
    ArticleFictif(
        "2000000000028",
        "Spaghetti n°5",
        "Pastissimo",
        "500 g",
        135,
        "pates spaghetti",
        0.5,
        "kg",
    ),
    ArticleFictif(
        "2000000000035",
        "Penne rigate",
        "Pastissimo",
        "500 g",
        135,
        "pates penne",
        0.5,
        "kg",
    ),
    ArticleFictif("2000000000042", "Riz long grain", "Rizière d'Or", "1 kg", 229, "riz", 1.0, "kg"),
    ArticleFictif(
        "2000000000059",
        "Œufs de poules élevées en plein air x12",
        "Ferme des Prés",
        "12 œufs",
        389,
        "oeufs",
    ),
    ArticleFictif(
        "2000000000066",
        "Beurre doux",
        "Laiterie du Bocage",
        "250 g",
        279,
        "beurre",
        0.25,
        "kg",
    ),
    ArticleFictif(
        "2000000000073",
        "Yaourts nature x8",
        "Laiterie du Bocage",
        "8 x 125 g",
        189,
        "yaourt nature",
        1.0,
        "kg",
    ),
    ArticleFictif(
        "2000000000080",
        "Pain de mie complet",
        "Bonjour Matin",
        "500 g",
        219,
        "pain de mie",
        0.5,
        "kg",
    ),
    ArticleFictif(
        "2000000000097",
        "Emmental râpé",
        "Fromagerie Comtoise",
        "200 g",
        239,
        "fromage rape emmental",
        0.2,
        "kg",
    ),
    ArticleFictif(
        "2000000000103",
        "Sauce tomate au basilic",
        "Pastissimo",
        "400 g",
        189,
        "sauce tomate",
        0.4,
        "kg",
    ),
    ArticleFictif(
        "2000000000110",
        "Bananes",
        "Vergers du Sud",
        "1 kg",
        199,
        "banane fruit",
        1.0,
        "kg",
    ),
    ArticleFictif(
        "2000000000127",
        "Papier toilette x12",
        "Douceur",
        "12 rouleaux",
        449,
        "papier toilette",
    ),
]

# Courses courantes, EAN et marques fictifs : (libellé, marque, quantité, prix, mots-clés, contenance,
# unité). Le premier mot du libellé est le produit lui-même (règle du « moins cher »).
_COURANTS = [
    ("Avocat x2", "Vergers du Sud", "2 pièces", 229, "avocats fruit", None, None),
    ("Pommes golden", "Vergers du Sud", "1 kg", 249, "fruit", 1.0, "kg"),
    ("Patates (pommes de terre)", "Vergers du Sud", "2,5 kg", 349, "legume", 2.5, "kg"),
    ("Tomates grappe", "Vergers du Sud", "1 kg", 279, "legume", 1.0, "kg"),
    ("Carottes", "Vergers du Sud", "1 kg", 149, "legume", 1.0, "kg"),
    ("Oignons jaunes", "Vergers du Sud", "1 kg", 179, "legume", 1.0, "kg"),
    ("Salade verte", "Vergers du Sud", "1 pièce", 119, "laitue legume", None, None),
    ("Crème fraîche épaisse", "Laiterie du Bocage", "20 cl", 119, "", 0.2, "L"),
    ("Fromage blanc nature", "Laiterie du Bocage", "1 kg", 239, "", 1.0, "kg"),
    ("Carré frais 0 %", "Fromagerie Comtoise", "8 x 25 g", 219, "fromage", 0.2, "kg"),
    ("Jambon blanc 4 tranches", "Maison Kerlan", "160 g", 269, "porc", 0.16, "kg"),
    ("Poulet en filets", "Maison Kerlan", "500 g", 599, "viande blanc", 0.5, "kg"),
    ("Steaks hachés x4", "Maison Kerlan", "400 g", 499, "steak viande boeuf", 0.4, "kg"),
    ("Thon au naturel", "Marée Haute", "140 g", 219, "poisson conserve", 0.14, "kg"),
    ("Pizza jambon fromage", "Bella Notte", "400 g", 329, "", 0.4, "kg"),
    ("Frites surgelées", "Maison Kerlan", "1 kg", 229, "frite", 1.0, "kg"),
    ("Glace vanille", "Bella Notte", "500 g", 329, "dessert", 0.5, "kg"),
    ("Farine de blé", "Moulin Doré", "1 kg", 99, "", 1.0, "kg"),
    ("Sucre en poudre", "Moulin Doré", "1 kg", 179, "", 1.0, "kg"),
    ("Sel fin", "Marée Haute", "750 g", 69, "", 0.75, "kg"),
    ("Huile de tournesol", "Moulin Doré", "1 L", 229, "", 1.0, "L"),
    ("Huile d'olive vierge extra", "Moulin Doré", "75 cl", 799, "", 0.75, "L"),
    ("Moutarde de Dijon", "Moulin Doré", "370 g", 149, "", 0.37, "kg"),
    ("Mayonnaise", "Moulin Doré", "235 g", 199, "sauce", 0.235, "kg"),
    ("Baguette", "Bonjour Matin", "250 g", 95, "pain", 0.25, "kg"),
    ("Céréales pétales de maïs", "Bonjour Matin", "500 g", 249, "petit dejeuner", 0.5, "kg"),
    ("Biscuits petit beurre", "Bonjour Matin", "200 g", 129, "gateau", 0.2, "kg"),
    ("Compote de pommes x8", "Vergers du Sud", "8 x 100 g", 219, "dessert", 0.8, "kg"),
    ("Chocolat noir", "Cacao & Cie", "200 g", 199, "tablette", 0.2, "kg"),
    ("Chips nature", "Bella Notte", "150 g", 159, "aperitif", 0.15, "kg"),
    ("Eau minérale 6 x 1,5 L", "Source Claire", "6 x 1,5 L", 329, "boisson", 9.0, "L"),
    ("Jus d'orange", "Vergers du Sud", "1 L", 199, "boisson", 1.0, "L"),
    ("Thé vert", "Cacao & Cie", "25 sachets", 189, "boisson", None, None),
    ("Shampooing doux", "Douceur", "300 ml", 289, "shampoing hygiene", 0.3, "L"),
    ("Gel douche", "Douceur", "250 ml", 199, "savon hygiene", 0.25, "L"),
    ("Dentifrice menthe", "Douceur", "75 ml", 179, "hygiene", 0.075, "L"),
    ("Mouchoirs x10 paquets", "Douceur", "10 paquets", 169, "mouchoir", None, None),
    ("Lessive liquide", "Net & Clair", "1,5 L", 599, "linge entretien", 1.5, "L"),
    ("Liquide vaisselle", "Net & Clair", "500 ml", 149, "entretien", 0.5, "L"),
]
_CATALOGUE_BASE += [
    ArticleFictif(f"200000000{numero:04d}", *champs)
    for numero, champs in enumerate(_COURANTS, start=200)
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
        f"Marque distributeur {enseigne.nom}",
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

_RUES = ["rue de Rennes", "avenue du Général de Gaulle", "rue de la Gare", "route de Nantes"]


def empreinte(*parties: object) -> int:
    """Entier stable (contrairement à hash(), qui change à chaque lancement de Python)."""
    texte = "|".join(str(p) for p in parties)
    return int(hashlib.sha256(texte.encode("utf-8")).hexdigest()[:12], 16)


def normaliser(texte: str) -> str:
    """Minuscules sans accents, pour comparer des recherches."""
    texte = texte.replace("œ", "oe").replace("Œ", "oe")
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().replace("'", " ").split())


_UNITES = {"kg", "gr", "ml", "cl"}


def rechercher_catalogue(recherche: str) -> list[ArticleFictif]:
    """Articles dont le texte a un mot commençant par chacun des mots de la recherche. Les quantités
    (« 400 g », « 20 cl », « x12 ») sont ignorées ; un EAN reste un EAN."""
    mots = [
        m
        for m in normaliser(recherche).split()
        if len(m) >= 2
        and m not in _UNITES
        and (not re.search(r"\d", m) or re.fullmatch(r"\d{8,14}", m))
    ]
    if not mots:
        return []
    resultats = []
    for article in CATALOGUE:
        texte = normaliser(f"{article.libelle} {article.marque} {article.mots_cles} {article.ean}")
        if all(any(t.startswith(mot) for t in texte.split()) for mot in mots):
            resultats.append(article)
    return resultats


def _article_generique(libelle: str, ean: str = "") -> ArticleFictif:
    """Article hors catalogue : même prix de base d'un lancement à l'autre, sans marque ni format."""
    ean = ean or f"2{empreinte(normaliser(libelle)) % 10**12:012d}"
    return ArticleFictif(ean, libelle, "", "", 150 + empreinte(ean) % 500)


class SourceFictive(SourcePrix):
    type_source = TypeSource.FICTIVE
    nom = LIBELLE_SOURCE

    def __init__(self, enseigne: Enseigne, delai_max_s: float = 0.0) -> None:
        self.enseigne = enseigne
        self.delai_max_s = delai_max_s
        self._requetes = 0

    async def _patienter(self) -> None:
        self._requetes += 1
        if self.delai_max_s > 0 and self._requetes <= REQUETES_RETARDEES:
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
            id_enseigne = f"m{h % 100000}"
            magasins.append(
                Magasin(
                    id=Magasin.fabriquer_id(self.enseigne, id_enseigne),
                    enseigne=self.enseigne,
                    id_enseigne=id_enseigne,
                    nom=nom,
                    adresse=f"{1 + h % 90} {_RUES[h % len(_RUES)]}",
                    position=Position(lat=lat, lon=lon),
                    est_fictif=True,
                )
            )
        return magasins

    async def chercher_produits(
        self, magasin: Magasin, recherche: str, limite: int = 20
    ) -> list[Prix]:
        await self._patienter()
        articles = [
            a for a in rechercher_catalogue(recherche) if a.exclusif in (None, self.enseigne)
        ]
        if not articles:
            texte = " ".join(recherche.split())
            if not texte:
                return []
            articles = [_article_generique(texte[:1].upper() + texte[1:])]
        offres = [self._prix_article(magasin, article) for article in articles]
        return sorted(offres, key=lambda p: p.prix_centimes)[:limite]

    async def obtenir_prix(self, magasin: Magasin, ean: str) -> Prix | None:
        await self._patienter()
        # EAN hors catalogue (ex. produit venu d'Open Food Facts) : le nom est inconnu ici, l'orchestrateur
        # reprend celui de la ligne de la liste.
        article = CATALOGUE_PAR_EAN.get(ean) or _article_generique("", ean)
        return self._prix_article(magasin, article)

    def _prix_article(self, magasin: Magasin, article: ArticleFictif) -> Prix:
        h = empreinte(magasin.id, article.ean)
        propre = article.exclusif == self.enseigne
        facteur = 1.0 if propre else _FACTEURS_ENSEIGNE[self.enseigne]
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
            source_detail=LIBELLE_AFFICHE,
            releve_le=datetime.now(UTC),
            # Affiché comme un relevé importé : « 28/11/2026 », sans l'heure.
            date_releve_source=datetime.now(ZoneInfo("Europe/Paris")).date(),
            est_fictif=True,
        )
