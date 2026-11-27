"""Préférences et estimations de trajet pour les magasins de proximité."""

from dataclasses import dataclass
from math import ceil

from app.contrats import Position
from app.magasins.service import distance_km


@dataclass(frozen=True)
class ModeTrajet:
    nom: str
    rayon: float
    vitesse: float
    attente: int = 0


MODES = {
    "voiture": ModeTrajet("Voiture", 15, 35),
    "transport": ModeTrajet("Transport en commun", 6, 18, 8),
    "velo": ModeTrajet("Vélo", 3, 15),
    "pied": ModeTrajet("À pied", 1.5, 4.5),
}


def estimer(depart: Position, arrivee: Position, mode: ModeTrajet, rayon: float) -> dict:
    distance = distance_km(depart, arrivee)
    return {
        "distance": distance,
        "minutes": max(1, ceil(distance * 1.25 * 60 / mode.vitesse + mode.attente)),
        "badge": "Proche pour ce mode" if distance <= rayon / 2 else "Dans le rayon choisi",
    }
