import re
import unicodedata
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.gabarits import PARIS

DriveId = Literal["coursesu-33315", "intermarche-05052"]
DRIVES: dict[DriveId, tuple[str, str, tuple[str, ...]]] = {
    "coursesu-33315": ("Super U Bruz", "12 place de Bretagne", ("coursesu.com",)),
    "intermarche-05052": (
        "Intermarché Super Bruz Cap Vert",
        "2 place Robert Barré, CC Cap Vert",
        ("intermarche.com", "intermarche.fr"),
    ),
}
Texte = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Montant = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=4)]
Erreur = Literal["mauvais_drive", "page_inattendue", "reseau", "delai", "403", "429", "defi", "404"]


def normaliser(texte: str) -> str:
    texte = "".join(
        c for c in unicodedata.normalize("NFKD", texte.casefold()) if not unicodedata.combining(c)
    )
    texte = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", texte)
    texte = re.sub(r"(?<=\d)\s*(?=(?:ml|cl|l|kg|g)\b)", "", texte)
    return " ".join(re.findall(r"[a-z0-9]+(?:[.,][0-9]+)?", texte.replace(",", ".")))


def ean_valide(ean: str) -> bool:
    return bool(re.fullmatch(r"(?:[0-9]{8}|[0-9]{12,14})", ean)) and (
        any(c != "0" for c in ean)
        and sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(reversed(ean))) % 10 == 0
    )


def url_marchande(drive: DriveId, url: str) -> str:
    parsed = urlsplit(url)
    hote = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.netloc != hote
        or not any(hote == d or hote.endswith("." + d) for d in DRIVES[drive][2])
    ):
        raise ValueError("Lien marchand hors du périmètre du drive.")
    return urlunsplit((parsed.scheme, hote, parsed.path or "/", "", ""))


def date_tri(releve_le: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", releve_le):
        instant = datetime.combine(date.fromisoformat(releve_le), time.min, PARIS)
    else:
        instant = datetime.fromisoformat(releve_le)
        if instant.tzinfo is None:
            raise ValueError("Fuseau horaire du relevé manquant.")
    return instant.astimezone(UTC).isoformat(timespec="microseconds")


class Recherche(BaseModel):
    q: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    drives: Annotated[list[DriveId], Field(min_length=1, max_length=2)]

    @field_validator("q")
    @classmethod
    def valider_requete(cls, valeur: str) -> str:
        if not normaliser(valeur):
            raise PydanticCustomError("recherche_vide", "Saisissez un produit ou un EAN.")
        return " ".join(valeur.split())

    @property
    def cle(self) -> str:
        return normaliser(self.q)


class ProduitObserve(BaseModel):
    produit: Annotated[Texte, Field(min_length=1)]
    prix_eur: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
    url: Annotated[str, StringConstraints(max_length=1800)]
    ean: Annotated[str, StringConstraints(max_length=32)] = ""
    id_produit_source: Texte = ""
    marque: Texte = ""
    variante: Texte = ""
    format: Texte = ""
    prix_par_unite_eur: Montant | None = None
    unite: Texte = ""
    devise: Literal["EUR"] = "EUR"
    promos: Texte = ""
    promos_json: Annotated[str, StringConstraints(max_length=8000)] = ""

    @field_validator("prix_eur", "prix_par_unite_eur", mode="before")
    @classmethod
    def lire_montant(cls, valeur: object) -> object:
        if isinstance(valeur, str):
            return valeur.strip().replace(",", ".") or None
        return valeur


class Depot(BaseModel):
    drive_id: DriveId
    bail: Annotated[str, StringConstraints(min_length=32, max_length=64)]
    etat: Literal["succes", "vide", "echec"]
    service_observe: Annotated[str, StringConstraints(max_length=80)] = ""
    erreur: Erreur | None = None
    produits: Annotated[list[ProduitObserve], Field(max_length=60)] = Field(default_factory=list)

    @model_validator(mode="after")
    def valider_etat(self):
        if bool(self.produits) != (self.etat == "succes"):
            raise PydanticCustomError("produits_invalides", "Produits incompatibles avec l'état.")
        if bool(self.erreur) != (self.etat == "echec"):
            raise PydanticCustomError("erreur_invalide", "Cause incompatible avec l'état.")
        return self
