import json
import re
import unicodedata
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.gabarits import PARIS

EnseigneDrive = Literal["coursesu", "intermarche"]
DOMAINES = {"coursesu": ("coursesu.com",), "intermarche": ("intermarche.com", "intermarche.fr")}


class PointRetrait(BaseModel):
    nom: str
    osm: str
    adresse: str
    ville: str
    code_postal: str
    accueil: str
    libelles: list[str]
    coordonnees: tuple[float, float] | None = None


def valider_drive(drive: str) -> str:
    if drive not in DRIVES:
        raise PydanticCustomError("drive_inconnu", "Point de retrait non répertorié.")
    return drive


DriveId = Annotated[str, AfterValidator(valider_drive)]
Texte = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Montant = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=4)]
Erreur = Literal["mauvais_drive", "page_inattendue", "reseau", "delai", "403", "429", "defi", "404"]


_FORMAT = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:x|×|\*)?\s*\d*(?:[.,]\d+)?\s*"
    r"(?:kg|gr|g|mg|cl|ml|l|litres?|pi[eè]ces?|pcs|tranches?|rouleaux|sachets?|capsules?|dosettes?|%)?(?=\s|$|[*x×/])",
    re.I,
)
_BRUIT = re.compile(
    r"[*×/+·|()\[\]]|\b(?:x\d+|\d+x|lot de|pack de|lot|pack|le|la|les|de|du|des)\b", re.I
)


def terme_simplifie(texte: str, mots_max: int = 4) -> str:
    """Texte tapé dans la recherche d'un drive : seulement les mots du produit, sans quantités ni
    symboles, que les moteurs des drives ne comprennent pas. « carré frais 200gr*8 0% » → « carré frais »,
    « lait demi-écrémé 1 l » → « lait demi-écrémé ». Un EAN est gardé tel quel."""
    texte = " ".join((texte or "").split())
    if re.fullmatch(r"\d{8,14}", texte):
        return texte
    texte = re.sub(r"\bn\s*°\s*\d*|\bno\s*\d+\b", " ", texte, flags=re.I)  # « n°5 »
    texte = _FORMAT.sub(" ", texte)
    texte = _BRUIT.sub(" ", texte)
    mots = [m for m in texte.split() if len(m) > 1 and not any(c.isdigit() for c in m)]
    return " ".join(mots[:mots_max])


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
        or not any(hote == d or hote.endswith("." + d) for d in DOMAINES[drive.split("-", 1)[0]])
    ):
        raise ValueError("Lien marchand hors du périmètre du drive.")
    return urlunsplit((parsed.scheme, hote, parsed.path or "/", "", ""))


DRIVES = {
    drive: PointRetrait.model_validate(point)
    for drive, point in json.loads(
        Path(__file__).with_name("points_retrait.json").read_text(encoding="utf-8")
    ).items()
}
for identifiant, point in DRIVES.items():
    if not re.fullmatch(r"(?:coursesu|intermarche)-[a-z0-9_-]+", identifiant):
        raise ValueError(f"Identifiant de retrait invalide : {identifiant}")
    if url_marchande(identifiant, point.accueil) != point.accueil:
        raise ValueError(f"Adresse de retrait non canonique : {identifiant}")

DRIVES_OSM = {point.osm: drive for drive, point in DRIVES.items()}


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
    drives: Annotated[list[DriveId], Field(min_length=1, max_length=20)]

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
