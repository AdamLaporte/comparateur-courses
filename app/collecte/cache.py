"""Cache SQLite des prix collectés et des réponses des services ouverts (lot 4).

Prix (table `cache_prix`) : clé magasin + recherche, valables CACHE_TTL_MIN minutes.
- `lire_frais` : prix encore valide → évite la requête à la source.
- `lire_dernier` : dernier prix connu, même périmé → premier niveau du repli. Il est rendu avec
  `source=TypeSource.CACHE` et garde la date du relevé d'origine.
- `ecrire` : enregistre un prix réel (jamais de données fictives, jamais un prix déjà issu du cache).

Réponses (table `cache_reponse`) : JSON brut d'Open Prices ou d'Open Food Facts, avec la date de
réception. `lire_reponse(..., age_max_min=None)` rend la réponse même ancienne (secours hors ligne).

Le cache ne fait jamais échouer une recherche : une erreur SQLite est journalisée et ignorée.
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from app import db
from app.config import Reglages
from app.contrats import Enseigne, LigneListe, ModeLigne, Prix, TypeSource

logger = logging.getLogger(__name__)


def maintenant() -> datetime:
    return datetime.now(UTC)


def cle_recherche(ligne: LigneListe) -> str:
    if ligne.mode == ModeLigne.PRODUIT and ligne.ean:
        return f"ean:{ligne.ean}"
    return f"texte:{' '.join(ligne.recherche.lower().split())}"


def _cle(magasin_id: str, cle: str) -> str:
    return f"{magasin_id}|{cle}"


def _lire(reglages: Reglages, magasin_id: str, cle: str, frais: bool) -> Prix | None:
    requete = "SELECT contenu_json FROM cache_prix WHERE cle = ?"
    parametres: tuple = (_cle(magasin_id, cle),)
    if frais:
        requete += " AND expire_le > ?"
        parametres += (maintenant().isoformat(),)
    try:
        with db.connexion(reglages.db_path) as cnx:
            ligne = cnx.execute(requete, parametres).fetchone()
        return Prix.model_validate_json(ligne["contenu_json"]) if ligne else None
    except (sqlite3.Error, ValueError):
        logger.exception("Lecture du cache impossible (%s, %s)", magasin_id, cle)
        return None


def lire_frais(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str) -> Prix | None:
    """Prix encore valide (moins de CACHE_TTL_MIN minutes), tel qu'il a été relevé."""
    return _lire(reglages, magasin_id, cle, frais=True)


def lire_dernier(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str) -> Prix | None:
    """Dernier prix connu, même périmé, marqué comme venant du cache (avec sa date d'origine)."""
    prix = _lire(reglages, magasin_id, cle, frais=False)
    if prix is None:
        return None
    origine = prix.source_detail or prix.source.value
    return prix.model_copy(
        update={"source": TypeSource.CACHE, "source_detail": f"Dernier prix connu ({origine})"}
    )


def ecrire(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str, prix: Prix) -> None:
    if prix.est_fictif or prix.source in (TypeSource.FICTIVE, TypeSource.CACHE):
        return
    expire_le = maintenant() + timedelta(minutes=reglages.cache_ttl_min)
    try:
        with db.connexion(reglages.db_path) as cnx:
            cnx.execute(
                "INSERT OR REPLACE INTO cache_prix "
                "(cle, enseigne, magasin_id, recherche, contenu_json, source, releve_le, expire_le) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _cle(magasin_id, cle),
                    enseigne.value,
                    magasin_id,
                    cle,
                    prix.model_dump_json(),
                    prix.source.value,
                    prix.releve_le.isoformat(),
                    expire_le.isoformat(),
                ),
            )
    except sqlite3.Error:
        logger.exception("Écriture dans le cache impossible (%s, %s)", magasin_id, cle)


def lire_reponse(reglages: Reglages, cle: str, age_max_min: float | None) -> Any | None:
    """Réponse JSON enregistrée, si elle a moins de `age_max_min` minutes (None : quel que soit son âge)."""
    try:
        with db.connexion(reglages.db_path) as cnx:
            ligne = cnx.execute(
                "SELECT contenu_json, recu_le FROM cache_reponse WHERE cle = ?", (cle,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("Lecture du cache de réponses impossible (%s)", cle)
        return None
    if ligne is None:
        return None
    if age_max_min is not None:
        recu_le = datetime.fromisoformat(ligne["recu_le"])
        if maintenant() - recu_le > timedelta(minutes=age_max_min):
            return None
    return json.loads(ligne["contenu_json"])


def ecrire_reponse(reglages: Reglages, cle: str, contenu: Any) -> None:
    try:
        with db.connexion(reglages.db_path) as cnx:
            cnx.execute(
                "INSERT OR REPLACE INTO cache_reponse (cle, contenu_json, recu_le) VALUES (?, ?, ?)",
                (cle, json.dumps(contenu, ensure_ascii=False), maintenant().isoformat()),
            )
    except sqlite3.Error:
        logger.exception("Écriture dans le cache de réponses impossible (%s)", cle)
