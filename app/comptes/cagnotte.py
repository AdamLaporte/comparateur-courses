"""Économies cumulées par compte à partir des comparaisons confirmées."""

import json
from uuid import uuid4

from app.config import Reglages
from app.contrats import TotalMagasin
from app.db import connexion


def preparer(
    reglages: Reglages, utilisateur_id: int, totaux: list[TotalMagasin]
) -> tuple[str, int] | None:
    tarifs = {t.magasin.id: t.total_centimes for t in totaux if t.complet}
    nombre = len(tarifs)
    if nombre < 2:
        return None
    moyenne = (sum(tarifs.values()) + nombre // 2) // nombre
    ecarts = {magasin: moyenne - total for magasin, total in tarifs.items()}
    comparaison = uuid4().hex
    with connexion(reglages.db_path) as cnx:
        cnx.execute(
            """DELETE FROM comparaison_cagnotte
               WHERE utilisateur_id = ? AND montant_centimes IS NULL
                 AND cree_le < datetime('now', '-1 day')""",
            (utilisateur_id,),
        )
        resultat = cnx.execute(
            """INSERT INTO comparaison_cagnotte (id, utilisateur_id, ecarts_json)
               SELECT ?, id, ? FROM utilisateur WHERE id = ?""",
            (comparaison, json.dumps(ecarts), utilisateur_id),
        )
        return (comparaison, moyenne) if resultat.rowcount else None


def enregistrer(
    reglages: Reglages, utilisateur_id: int, comparaison: str, magasin_id: str
) -> bool:
    with connexion(reglages.db_path) as cnx:
        resultat = cnx.execute(
            """UPDATE comparaison_cagnotte
               SET montant_centimes = (SELECT value FROM json_each(ecarts_json) WHERE key = ?),
                   ecarts_json = '{}'
               WHERE id = ? AND utilisateur_id = ? AND montant_centimes IS NULL
                 AND cree_le >= datetime('now', '-1 day')
                 AND EXISTS (SELECT 1 FROM json_each(ecarts_json) WHERE key = ?)""",
            (magasin_id, comparaison, utilisateur_id, magasin_id),
        )
        return resultat.rowcount == 1


def solde(reglages: Reglages, utilisateur_id: int) -> int:
    with connexion(reglages.db_path) as cnx:
        return cnx.execute(
            """SELECT COALESCE(SUM(montant_centimes), 0) FROM comparaison_cagnotte
               WHERE utilisateur_id = ?""",
            (utilisateur_id,),
        ).fetchone()[0]
