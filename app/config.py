"""Réglages de l'application, lus dans `.env` (fichier partagé : ajouts concertés seulement).

Tous les réglages ont une valeur par défaut : le site marche sans `.env`, avec les données fictives.
Modèle des variables : `.env.example`.
"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contrats import Enseigne

RACINE = Path(__file__).resolve().parent.parent


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RACINE / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Source de prix par enseigne : "fictive" (défaut), "api" (Intermarché),
    # "collecte" (Carrefour, E.Leclerc Drive, Courses U).
    source_carrefour: str = "fictive"
    source_intermarche: str = "fictive"
    source_coursesu: str = "fictive"
    source_leclerc: str = "fictive"

    # Magasins interrogés autour du code postal.
    rayon_km: float = 10.0
    max_magasins_par_enseigne: int = 2
    # Vrais magasins tirés d'OpenStreetMap (data/magasins/osm.json) ; sinon, ceux des sources (fictifs).
    magasins_osm: bool = True
    # Rayon choisi par l'utilisateur : tous les magasins dans le rayon, au plus ce nombre par enseigne.
    max_magasins_par_enseigne_rayon: int = 5

    # Collecte : limites par enseigne et cache.
    timeout_enseigne_s: float = 6.0
    timeout_requete_s: float = 5.0
    concurrence_par_enseigne: int = 3
    cache_ttl_min: int = 360
    drives_fraicheur_min: int = 1440
    drives_jeton: str = ""
    # Délai aléatoire maximal de la source fictive, pour voir l'affichage progressif (0 dans les tests).
    delai_fictif_max_s: float = 0.8

    # Intermarché : clé vide tant que la demande n'est pas approuvée. Vide = aucune requête.
    intermarche_api_key: str = ""
    intermarche_url_stores: str = "https://api-partners.intermarche.com/v1"
    intermarche_url_produits: str = "https://api-partners.intermarche.com/produits/v1"

    # Services ouverts.
    open_prices_url: str = "https://prices.openfoodfacts.org/api/v1"
    open_food_facts_url: str = "https://world.openfoodfacts.org"
    # Recherche texte d'Open Food Facts (search-a-licious) : la recherche classique renvoie souvent 503.
    open_food_facts_recherche_url: str = "https://search.openfoodfacts.org"
    # Référentiel produits : "open_food_facts" (défaut) ou "fictive" (catalogue fictif, sans réseau).
    source_produits: str = "open_food_facts"
    # Open Prices comme source de secours du repli (False = aucune requête, ex. dans les tests).
    open_prices_actif: bool = True
    api_adresse_url: str = "https://data.geopf.fr/geocodage"
    # User-Agent des appels aux services ouverts (Open Food Facts le demande). Pas d'e-mail ici.
    user_agent_services: str = "ComparateurCourses/0.1 (hackathon ENSAI)"

    # E-mails (lien « mot de passe perdu »). SMTP_HOTE vide = lien écrit dans le journal du serveur.
    smtp_hote: str = ""
    smtp_port: int = 587
    smtp_utilisateur: str = ""
    smtp_mot_de_passe: str = ""
    smtp_expediteur: str = ""

    # Application.
    secret_key: str = "dev-secret-a-changer"
    db_path: Path = Path("data/app.db")

    @field_validator("db_path")
    @classmethod
    def _chemin_absolu(cls, chemin: Path) -> Path:
        return chemin if chemin.is_absolute() else RACINE / chemin

    def source_pour(self, enseigne: Enseigne) -> str:
        """Nom de la source configurée pour une enseigne (ex. "fictive", "collecte")."""
        return getattr(self, f"source_{enseigne.value}").strip().lower()

    @property
    def mode_fictif_actif(self) -> bool:
        """Vrai si au moins une enseigne utilise des données fictives (bandeau affiché)."""
        return any(self.source_pour(e) == "fictive" for e in Enseigne)


def reglages_requete(request: Request) -> Reglages:
    """Dépendance FastAPI : les réglages de l'application en cours (remplaçables dans les tests)."""
    return request.app.state.reglages


# À utiliser dans les routes : `reglages: ReglagesDep`.
ReglagesDep = Annotated[Reglages, Depends(reglages_requete)]
