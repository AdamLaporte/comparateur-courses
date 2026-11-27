"""Moteur de templates Jinja2 commun et filtres d'affichage (fichier partagé : ajouts concertés).

Les templates sont dans app/templates/ : base.html + un dossier par fonctionnalité.
Les fragments HTMX ont un nom qui commence par « _ ».
"""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

PARIS = ZoneInfo("Europe/Paris")

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


def euros(centimes: int | None) -> str:
    """1234 → « 12,34 € »."""
    if centimes is None:
        return "–"
    signe = "-" if centimes < 0 else ""
    centimes = abs(centimes)
    return f"{signe}{centimes // 100},{centimes % 100:02d} €"


def releve(moment: datetime | None) -> str:
    """Heure du relevé à Paris : « 15:42 » aujourd'hui, sinon « 26/11 15:42 »."""
    if moment is None:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(PARIS)
    if local.date() == datetime.now(PARIS).date():
        return local.strftime("%H:%M")
    return local.strftime("%d/%m %H:%M")


templates.env.filters["euros"] = euros
templates.env.filters["releve"] = releve


def rendre(nom: str, **contexte: object) -> str:
    """Rend un template en texte (pour les fragments envoyés par SSE)."""
    return templates.env.get_template(nom).render(**contexte)
