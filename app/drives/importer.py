import argparse
import csv
from pathlib import Path

from app import db
from app.config import Reglages
from app.drives.modeles import DRIVES, ProduitObserve, normaliser
from app.drives.service import observer


def importer(chemin_db: Path, chemin_csv: Path) -> tuple[int, int]:
    with (
        chemin_csv.open(encoding="utf-8-sig", newline="") as fichier,
        db.connexion(chemin_db) as cnx,
    ):
        lecteur = csv.DictReader(fichier, delimiter=";")
        requis = {"service_drive", "drive", "releve_le", "produit", "prix_eur", "url"}
        if not requis.issubset(lecteur.fieldnames or []):
            raise ValueError("L'en-tête du CSV est incomplet.")
        avant = cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0]
        total = 0
        for ligne in lecteur:
            try:
                drive = next(
                    d
                    for d, point in DRIVES.items()
                    if d.split("-", 1)[1] == ligne["service_drive"].strip()
                    and normaliser(point.nom) == normaliser(ligne["drive"])
                )
                champs = {
                    champ: (ligne[champ] or "").strip()
                    for champ in ProduitObserve.model_fields
                    if champ in ligne
                }
                if champs.get("promos", "").startswith(("'-", "'+", "'=", "'@")):
                    champs["promos"] = champs["promos"][1:]
                produit = ProduitObserve.model_validate(champs)
                observer(cnx, drive, produit, ligne["releve_le"].strip(), "CSV")
            except (StopIteration, ValueError, AttributeError) as exc:
                raise ValueError(
                    f"{chemin_csv.name}, ligne {lecteur.line_num} : retrait ou observation invalide."
                ) from exc
            total += 1
        apres = cnx.execute("SELECT count(*) FROM drive_observation").fetchone()[0]
    return total, apres - avant


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importer des relevés CSV des points de retrait répertoriés."
    )
    parser.add_argument("fichiers", nargs="+", type=Path)
    args = parser.parse_args()
    chemin_db = Reglages().db_path
    db.initialiser(chemin_db)
    for chemin in args.fichiers:
        try:
            total, ajoutes = importer(chemin_db, chemin)
        except (OSError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
        print(f"{chemin.name} : {total} lignes, {ajoutes} observations ajoutées.")


if __name__ == "__main__":
    main()
