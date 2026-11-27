"""Liste de courses enregistrée dans SQLite, liée à la session (sans compte) ou à l'utilisateur.

Clés de session utilisées : "sid" (identifiant de session anonyme), "code_postal",
"utilisateur_id" (posée par le module comptes à la connexion).
"""

import uuid

from fastapi import Request

from app import db
from app.config import Reglages
from app.contrats import AjoutLigne, LigneListe


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
