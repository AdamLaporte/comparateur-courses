"""Contrat de l'application : schémas Pydantic partagés.

Fichier partagé : modification concertée seulement (ajouts annoncés dans docs/decisions.md).
Conventions : montants en centimes entiers, dates en UTC, données fictives toujours marquées.
"""

import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Enseigne(StrEnum):
    CARREFOUR = "carrefour"
    INTERMARCHE = "intermarche"
    COURSES_U = "coursesu"
    LECLERC = "leclerc"

    @property
    def nom(self) -> str:
        return NOMS_ENSEIGNES[self]


NOMS_ENSEIGNES = {
    Enseigne.CARREFOUR: "Carrefour",
    Enseigne.INTERMARCHE: "Intermarché",
    Enseigne.COURSES_U: "Courses U",
    Enseigne.LECLERC: "E.Leclerc Drive",
}


class TypeSource(StrEnum):
    API = "api"
    COLLECTE = "collecte"
    OPEN_PRICES = "open_prices"
    CACHE = "cache"
    FICTIVE = "fictive"


class ModeLigne(StrEnum):
    PRODUIT = "produit"  # produit précis, identifié par son EAN
    EQUIVALENT = "equivalent"  # le moins cher qui correspond à la recherche, dans chaque magasin
    INEXISTANT = "inexistant"  # lu sur un ticket, introuvable en magasin : gardé dans la liste, jamais comparé


class StatutPrix(StrEnum):
    TROUVE = "trouve"
    INTROUVABLE = "introuvable"  # le magasin a répondu : il n'a pas ce produit
    INDISPONIBLE = "indisponible"  # pas de réponse exploitable (échec, délai, pas de clé…)
    EN_ATTENTE = "en_attente"


class TypePromo(StrEnum):
    IMMEDIATE = "immediate"  # déjà déduite de Prix.prix_centimes, sert à afficher l'économie
    LOT = "lot"  # ex. « le 2e à -50 % » : remise par groupe de quantite_min articles
    FIDELITE = "fidelite"  # carte de fidélité : non déduite tant que la carte n'est pas déclarée


class Position(BaseModel):
    lat: float
    lon: float


class Magasin(BaseModel):
    id: str  # "<enseigne>-<id_enseigne>", utilisable dans le HTML et les noms d'événements SSE
    enseigne: Enseigne
    id_enseigne: str
    nom: str
    adresse: str = ""
    code_postal: str = ""
    ville: str = ""
    position: Position
    distance_km: float | None = None
    est_fictif: bool = False

    @staticmethod
    def fabriquer_id(enseigne: Enseigne, id_enseigne: str) -> str:
        return f"{enseigne.value}-{re.sub(r'[^A-Za-z0-9]+', '-', id_enseigne).strip('-')}"


class Produit(BaseModel):
    ean: str | None = None
    libelle: str
    marque: str | None = None
    quantite: str | None = None  # ex. "1 L", "400 g"


class Promotion(BaseModel):
    libelle: str
    type: TypePromo
    remise_centimes: int = 0  # remise par déclenchement (par groupe de quantite_min articles)
    quantite_min: int = Field(1, ge=1)
    fin: date | None = None


class Prix(BaseModel):
    magasin_id: str
    produit: Produit
    prix_centimes: (
        int  # prix payé en caisse pour une unité, sans condition (promo immédiate déduite)
    )
    prix_barre_centimes: int | None = None  # ancien prix si promotion immédiate
    prix_unitaire_centimes: int | None = None  # au kilo, au litre…
    unite: str | None = None  # "kg", "L"…
    promotions: list[Promotion] = []
    source: TypeSource
    source_detail: str = (
        ""  # libellé affiché, ex. "Données fictives", "Intermarché (API officielle)"
    )
    releve_le: datetime  # UTC
    est_fictif: bool = False


class LigneListe(BaseModel):
    id: int
    mode: ModeLigne
    ean: str | None = None
    recherche: str
    libelle: str
    quantite: int = Field(1, ge=1, le=99)


class AjoutLigne(BaseModel):
    mode: ModeLigne
    ean: str | None = None
    recherche: str = Field(min_length=1, max_length=120)
    libelle: str | None = None
    quantite: int = Field(1, ge=1, le=99)

    @model_validator(mode="after")
    def _ean_si_produit(self) -> "AjoutLigne":
        if self.mode == ModeLigne.PRODUIT and not self.ean:
            raise ValueError("une ligne « produit » doit avoir un EAN")
        return self


class ResultatLigne(BaseModel):
    ligne_id: int
    magasin_id: str
    statut: StatutPrix
    prix: Prix | None = None
    sous_total_centimes: int | None = None  # rempli par app/panier/calcul.py
    economies_centimes: int = 0
    remarque: str | None = None  # message court pour l'utilisateur, ex. "dernier prix connu"


class TotalMagasin(BaseModel):
    magasin: Magasin
    total_centimes: int
    economies_centimes: int
    nb_trouves: int
    nb_manquants: int  # introuvables + indisponibles
    nb_en_attente: int = 0
    complet: bool
    rang: int | None = None  # 1 = panier le moins cher (complets d'abord)


class EvenementPrix(BaseModel):
    resultat: ResultatLigne


class MagasinsReponse(BaseModel):
    code_postal: str
    ville: str
    position: Position
    magasins: list[Magasin]
    enseignes_sans_magasin: list[Enseigne] = []
    rayon_km: float | None = None  # None : les plus proches de chaque enseigne


class DemandeTotaux(BaseModel):
    code_postal: str = Field(pattern=r"^\d{5}$")
    lignes: list[AjoutLigne] = Field(min_length=1, max_length=50)


class TotauxReponse(BaseModel):
    lignes: list[LigneListe]
    magasins: list[Magasin]
    resultats: list[ResultatLigne]
    totaux: list[TotalMagasin]
