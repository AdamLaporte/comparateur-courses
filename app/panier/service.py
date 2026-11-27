"""Liste de courses enregistrée dans SQLite, liée à la session (sans compte) ou à l'utilisateur.

Clés de session utilisées : "sid" (identifiant de session anonyme), "code_postal",
"utilisateur_id" (posée par le module comptes à la connexion).
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, Request

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


def listes(reglages: Reglages, compte: str) -> dict[str, str]:
    """La liste principale conserve la clé historique de ses articles."""
    with db.connexion(reglages.db_path) as cnx:
        lignes = cnx.execute(
            "SELECT cle, nom FROM liste_courses WHERE proprietaire = ? ORDER BY rowid", (compte,)
        )
        return {compte: "Ma liste", **{ligne["cle"]: ligne["nom"] for ligne in lignes}}


def cle_liste(request: Request, reglages: Reglages, creer: bool = True) -> str | None:
    compte = proprietaire(request, creer)
    if compte is None:
        return None
    explicite = request.headers.get("X-Liste-Courses") or request.query_params.get("liste")
    identifiant = explicite or request.session.get("liste_active")
    if not identifiant or identifiant == "principale":
        return compte
    if identifiant in listes(reglages, compte):
        return identifiant
    if explicite:
        raise HTTPException(404, "Liste introuvable.")
    request.session.pop("liste_active", None)
    return compte


def enregistrer_liste(reglages: Reglages, compte: str, nom: str, cle: str | None = None) -> str:
    nom = nom.strip()
    if not 1 <= len(nom) <= 60:
        raise ValueError("Le nom doit contenir entre 1 et 60 caractères.")
    if cle is None:
        cle = f"liste:{uuid.uuid4().hex}"
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            """INSERT INTO liste_courses (cle, proprietaire, nom) VALUES (?, ?, ?)
               ON CONFLICT(cle) DO UPDATE SET nom = excluded.nom
               WHERE proprietaire = excluded.proprietaire""",
            (cle, compte, nom),
        )
    return cle


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


def lire(reglages: Reglages, proprietaire: str | None, ligne_id: int) -> LigneListe | None:
    if proprietaire is None:
        return None
    with db.connexion(reglages.db_path) as cnx:
        ligne = cnx.execute(
            "SELECT id, mode, ean, recherche, libelle, quantite FROM ligne_liste "
            "WHERE id = ? AND proprietaire = ?",
            (ligne_id, proprietaire),
        ).fetchone()
    return LigneListe(**dict(ligne)) if ligne else None


def changer_quantite(reglages: Reglages, proprietaire: str, ligne_id: int, quantite: int) -> None:
    if not 1 <= quantite <= 99:
        return
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "UPDATE ligne_liste SET quantite = ? WHERE id = ? AND proprietaire = ?",
            (quantite, ligne_id, proprietaire),
        )


def vider(reglages: Reglages, proprietaire: str) -> list[LigneListe]:
    """Vide la liste et rend les lignes retirées (pour pouvoir annuler)."""
    retirees = lister(reglages, proprietaire)
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute("DELETE FROM ligne_liste WHERE proprietaire = ?", (proprietaire,))
    return retirees


def restaurer(reglages: Reglages, proprietaire: str, lignes: list[LigneListe]) -> int:
    """Remet des lignes retirées (bouton « Annuler »), à leur place d'origine quand leur numéro est
    encore libre, sinon en fin de liste."""
    colonnes = "proprietaire, mode, ean, recherche, libelle, quantite"
    with db.connexion(reglages.db_path) as cnx:
        for ligne in lignes:
            valeurs = (
                proprietaire,
                ligne.mode.value,
                ligne.ean,
                ligne.recherche,
                ligne.libelle,
                ligne.quantite,
            )
            libre = cnx.execute("SELECT 1 FROM ligne_liste WHERE id = ?", (ligne.id,)).fetchone()
            if libre is None:
                cnx.execute(
                    f"INSERT INTO ligne_liste (id, {colonnes}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ligne.id, *valeurs),
                )
            else:
                cnx.execute(
                    f"INSERT INTO ligne_liste ({colonnes}) VALUES (?, ?, ?, ?, ?, ?)", valeurs
                )
    return len(lignes)
