"""Liste de courses enregistrée dans SQLite, liée à la session (sans compte) ou à l'utilisateur.

Clés de session utilisées : "sid" (identifiant de session anonyme), "code_postal",
"utilisateur_id" (posée par le module comptes à la connexion).
"""

import uuid
from pathlib import Path

from fastapi import Request

from app import db
from app.config import Reglages
from app.contrats import AjoutLigne, LigneListe, ModeLigne


def proprietaire(request: Request, creer: bool = True) -> str | None:
    """« utilisateur:<id> » si connecté, sinon « session:<uuid> » (créé au besoin)."""
    utilisateur_id = request.session.get("utilisateur_id")
    if utilisateur_id is not None:
        return f"utilisateur:{utilisateur_id}"
    sid = request.session.get("sid")
    if sid is None:
        if not creer:
            return None
        sid = uuid.uuid4().hex
        request.session["sid"] = sid
    return f"session:{sid}"


def migrer(chemin_db: Path) -> None:
    """Bases créées avant le mode « inexistant » : on recrée ligne_liste avec la nouvelle contrainte
    (SQLite ne sait pas modifier un CHECK), en gardant toutes les lignes."""
    with db.connexion(chemin_db) as cnx:
        ligne = cnx.execute("SELECT sql FROM sqlite_master WHERE name = 'ligne_liste'").fetchone()
        if ligne is None or "'inexistant'" in ligne["sql"]:
            return
        nouvelle = ligne["sql"].replace("'equivalent')", "'equivalent', 'inexistant')")
        cnx.execute("ALTER TABLE ligne_liste RENAME TO ligne_liste_avant")
        cnx.execute(nouvelle)
        cnx.execute("INSERT INTO ligne_liste SELECT * FROM ligne_liste_avant")
        cnx.execute("DROP TABLE ligne_liste_avant")
        cnx.execute(
            "CREATE INDEX IF NOT EXISTS idx_ligne_liste_proprietaire ON ligne_liste (proprietaire)"
        )


def lister(reglages: Reglages, proprietaire: str | None) -> list[LigneListe]:
    if proprietaire is None:
        return []
    with db.connexion(reglages.db_path) as cnx:
        lignes = cnx.execute(
            "SELECT id, mode, ean, recherche, libelle, quantite FROM ligne_liste "
            "WHERE proprietaire = ? ORDER BY id",
            (proprietaire,),
        ).fetchall()
    return [LigneListe(**dict(ligne)) for ligne in lignes]


def ajouter(reglages: Reglages, proprietaire: str, ajout: AjoutLigne) -> LigneListe:
    libelle = (ajout.libelle or ajout.recherche).strip()
    with db.connexion(reglages.db_path) as cnx:
        curseur = cnx.execute(
            "INSERT INTO ligne_liste (proprietaire, mode, ean, recherche, libelle, quantite) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                proprietaire,
                ajout.mode.value,
                ajout.ean,
                ajout.recherche.strip(),
                libelle,
                ajout.quantite,
            ),
        )
        ligne_id = curseur.lastrowid
    return LigneListe(
        id=ligne_id,
        mode=ajout.mode,
        ean=ajout.ean,
        recherche=ajout.recherche.strip(),
        libelle=libelle,
        quantite=ajout.quantite,
    )


def supprimer(reglages: Reglages, proprietaire: str, ligne_id: int) -> None:
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "DELETE FROM ligne_liste WHERE id = ? AND proprietaire = ?", (ligne_id, proprietaire)
        )


def changer_mode(reglages: Reglages, proprietaire: str, ligne_id: int, mode: ModeLigne) -> None:
    """Bascule une ligne entre « produit précis » et « le moins cher ». L'EAN est gardé en passant au
    moins cher, pour pouvoir revenir au produit choisi ; une ligne sans EAN ne peut pas devenir précise."""
    if mode not in (ModeLigne.PRODUIT, ModeLigne.EQUIVALENT):
        return
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "UPDATE ligne_liste SET mode = ? WHERE id = ? AND proprietaire = ? "
            "AND mode != 'inexistant' AND (? = 'equivalent' OR ean IS NOT NULL)",
            (mode.value, ligne_id, proprietaire, mode.value),
        )


def changer_mode_tout(reglages: Reglages, proprietaire: str, mode: ModeLigne) -> None:
    """Toute la liste au moins cher, ou retour aux produits choisis (lignes qui ont un EAN)."""
    depart = ModeLigne.PRODUIT if mode == ModeLigne.EQUIVALENT else ModeLigne.EQUIVALENT
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "UPDATE ligne_liste SET mode = ? WHERE proprietaire = ? AND mode = ? AND ean IS NOT NULL",
            (mode.value, proprietaire, depart.value),
        )
