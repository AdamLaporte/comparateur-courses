"""Moteur de templates Jinja2 commun et filtres d'affichage (fichier partagé : ajouts concertés).

Les templates sont dans app/templates/ : base.html + un dossier par fonctionnalité.
Les fragments HTMX ont un nom qui commence par « _ ».
"""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

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


def jour(prix) -> str:
    """Jour du relevé d'un prix, à Paris : « 28/11/2026 » (jamais l'heure)."""
    if prix.date_releve_source:
        return prix.date_releve_source.strftime("%d/%m/%Y")
    moment = prix.releve_le
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(PARIS).strftime("%d/%m/%Y")


def etiquette(centimes: int | None) -> Markup:
    """Grand prix façon étiquette de rayon : 1234 → 12 en gros, « ,34 € » en petit."""
    if centimes is None:
        return Markup("–")
    signe = "-" if centimes < 0 else ""
    centimes = abs(centimes)
    return Markup(
        f'<span class="etq">{signe}{centimes // 100}'
        f'<span class="etq-c">,{centimes % 100:02d}&nbsp;€</span></span>'
    )


templates.env.filters["euros"] = euros
templates.env.filters["releve"] = releve
templates.env.filters["etiquette"] = etiquette
templates.env.globals["jour"] = jour


DOSSIER_STATIQUE = Path(__file__).resolve().parent / "static"


def version_statique(chemin: str) -> str:
    """Date de modification d'un fichier de app/static/, ajoutée à son adresse (?v=…) : le navigateur
    recharge le CSS ou le JS dès qu'il change, au lieu de garder l'ancien en cache."""
    try:
        return str(int((DOSSIER_STATIQUE / chemin).stat().st_mtime))
    except OSError:
        return "0"


templates.env.globals["version_statique"] = version_statique


def rendre(nom: str, **contexte: object) -> str:
    """Rend un template en texte (pour les fragments envoyés par SSE)."""
    return templates.env.get_template(nom).render(**contexte)
