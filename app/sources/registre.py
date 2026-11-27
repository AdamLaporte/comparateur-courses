"""Choix de la source de chaque enseigne, d'après les réglages (SOURCE_CARREFOUR=fictive|collecte…).

Par défaut toutes les enseignes sont fictives : chaque lot active sa vraie source dans son `.env`
pendant que les autres restent fictives.
"""

from app.config import Reglages
from app.contrats import Enseigne
from app.sources.base import SourcePrix
from app.sources.carrefour import SourceCarrefour
from app.sources.coursesu import SourceCoursesU
from app.sources.fictive import SourceFictive
from app.sources.intermarche import SourceIntermarche
from app.sources.leclerc import SourceLeclerc

SOURCES_REELLES = {
    (Enseigne.INTERMARCHE, "api"): SourceIntermarche,
    (Enseigne.CARREFOUR, "collecte"): SourceCarrefour,
    (Enseigne.LECLERC, "collecte"): SourceLeclerc,
    (Enseigne.COURSES_U, "collecte"): SourceCoursesU,
}


def source_pour(enseigne: Enseigne, reglages: Reglages) -> SourcePrix:
    choix = reglages.source_pour(enseigne)
    if choix == "fictive":
        return SourceFictive(enseigne, reglages.delai_fictif_max_s)
    classe = SOURCES_REELLES.get((enseigne, choix))
    if classe is None:
        possibles = ["fictive"] + [c for (e, c) in SOURCES_REELLES if e == enseigne]
        raise ValueError(
            f"Source « {choix} » inconnue pour {enseigne.nom} : choisir parmi {possibles}"
        )
    return classe(reglages)


def sources_actives(reglages: Reglages) -> dict[Enseigne, SourcePrix]:
    return {enseigne: source_pour(enseigne, reglages) for enseigne in Enseigne}
