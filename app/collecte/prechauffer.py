"""Remplit le cache à l'avance à partir d'une liste de recherches, pour préparer la démo (lot 4).

Usage :
    uv run python -m app.collecte.prechauffer data/demo/recherches.txt --code-postal 35170

BOUCHON : la commande lit ses arguments mais ne fait encore rien. À implémenter dans le lot 4 :
géocoder le code postal, trouver les magasins (app.magasins.service.magasins_proches), puis pour chaque
recherche lancer app.collecte.orchestrateur.collecter avec des lignes « équivalent » ou « produit »
et laisser le cache enregistrer les prix réels. Requêtes modérées : respecter les limites par enseigne.
"""

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Préchauffe le cache des prix pour la démo.")
    parseur.add_argument(
        "fichier", type=Path, help="une recherche par ligne (ex. data/demo/recherches.txt)"
    )
    parseur.add_argument("--code-postal", required=True, help="code postal de la démo, ex. 35170")
    args = parseur.parse_args(argv)

    recherches = [
        ligne.strip()
        for ligne in args.fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    print(f"{len(recherches)} recherches lues pour le code postal {args.code_postal}.")
    print("Préchauffage pas encore implémenté (lot 4) : rien n'a été mis en cache.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
