"""Base SQLite (fichier partagé).

Chaque fonctionnalité déclare ses tables dans son propre fichier `app/<fonctionnalite>/schema.sql`
(`CREATE TABLE IF NOT EXISTS ...`). `initialiser` les exécute tous au démarrage : ajouter une table ne
demande donc jamais de modifier ce fichier.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DOSSIER_APP = Path(__file__).resolve().parent


def initialiser(chemin_db: Path) -> None:
    chemin_db.parent.mkdir(parents=True, exist_ok=True)
    with connexion(chemin_db) as cnx:
        cnx.execute("PRAGMA journal_mode=WAL")
        for schema in sorted(DOSSIER_APP.glob("*/schema.sql")):
            cnx.executescript(schema.read_text(encoding="utf-8"))


@contextmanager
def connexion(chemin_db: Path) -> Iterator[sqlite3.Connection]:
    """Ouvre une connexion, valide à la sortie (ou annule en cas d'erreur), puis la ferme."""
    cnx = sqlite3.connect(chemin_db, timeout=5)
    cnx.row_factory = sqlite3.Row
    cnx.execute("PRAGMA foreign_keys=ON")
    try:
        yield cnx
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cnx.close()
