"""Remplit le cache à l'avance à partir d'une liste de recherches, pour préparer la démo (lot 4).

Usage :
    uv run python -m app.collecte.prechauffer data/demo/recherches.txt --code-postal 35170

Pour le code postal donné :
1. trouve les magasins proches, avec les sources configurées dans `.env` ;
2. lance chaque recherche sur Open Food Facts (le cache des suggestions se remplit) ;
3. collecte les prix de chaque recherche dans chaque magasin, avec l'orchestrateur habituel : les prix
   réels (API, collecte) vont dans `cache_prix`, et les réponses Open Prices du repli dans
   `cache_reponse`. Les données fictives ne sont jamais mises en cache.

Une ligne du fichier est une recherche texte (mode « équivalent ») ou un EAN de 8 à 14 chiffres (mode
« produit »). Requêtes modérées : mêmes limites par enseigne que le site, mais pas de délai global
(le préchauffage n'est pas interactif).
"""

import argparse
import asyncio
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app import db
from app.collecte.orchestrateur import collecter
from app.config import Reglages
from app.contrats import LigneListe, ModeLigne, StatutPrix
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide
from app.magasins.service import magasins_proches
from app.produits.service import rechercher
from app.sources.registre import sources_actives

DELAI_PRECHAUFFAGE_S = 300.0  # par enseigne, au lieu de TIMEOUT_ENSEIGNE_S


def lire_recherches(fichier: Path) -> list[str]:
    return [
        ligne.strip()
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]


def lignes_depuis(recherches: list[str]) -> list[LigneListe]:
    lignes = []
    for i, recherche in enumerate(recherches, start=1):
        if re.fullmatch(r"\d{8,14}", recherche):
            lignes.append(
                LigneListe(
                    id=i,
                    mode=ModeLigne.PRODUIT,
                    ean=recherche,
                    recherche=recherche,
                    libelle=recherche,
                )
            )
        else:
            lignes.append(
                LigneListe(id=i, mode=ModeLigne.EQUIVALENT, recherche=recherche, libelle=recherche)
            )
    return lignes


async def prechauffer(recherches: list[str], code_postal: str, reglages: Reglages) -> int:
    db.initialiser(reglages.db_path)
    try:
        reponse = await magasins_proches(code_postal, reglages)
    except (CodePostalInvalide, CodePostalInconnu) as erreur:
        print(f"Code postal refusé : {erreur}")
        return 2
    magasins = reponse.magasins
    print(f"{reponse.ville} ({code_postal}) : {len(magasins)} magasins.")
    for magasin in magasins:
        source = reglages.source_pour(magasin.enseigne)
        print(f"  - {magasin.nom} [{magasin.id}], {magasin.distance_km} km, source {source}")
    if reponse.enseignes_sans_magasin:
        print("  Sans magasin : " + ", ".join(e.nom for e in reponse.enseignes_sans_magasin))
    fictives = [
        e.nom for e in {m.enseigne for m in magasins} if reglages.source_pour(e) == "fictive"
    ]
    if fictives:
        print(f"  (Données fictives, jamais mises en cache : {', '.join(sorted(fictives))})")

    lignes = lignes_depuis(recherches)
    textes = [ligne.recherche for ligne in lignes if ligne.mode == ModeLigne.EQUIVALENT]
    print(f"\nSuggestions d'articles : {len(textes)} recherches sur Open Food Facts…")
    for texte in textes:
        produits = await rechercher(texte, reglages)
        print(
            f"  - {texte} : {len(produits)} produits"
            + (f" ({produits[0].libelle})" if produits else "")
        )

    if not magasins:
        print("\nAucun magasin : rien à collecter.")
        return 1
    print(f"\nPrix : {len(lignes)} recherches × {len(magasins)} magasins…")
    reglages_longs = reglages.model_copy(update={"timeout_enseigne_s": DELAI_PRECHAUFFAGE_S})
    bilan: dict[str, Counter] = defaultdict(Counter)
    async for resultat in collecter(lignes, magasins, sources_actives(reglages), reglages_longs):
        if resultat.statut == StatutPrix.TROUVE and resultat.prix is not None:
            bilan[resultat.magasin_id][resultat.prix.source.value] += 1
        else:
            bilan[resultat.magasin_id][resultat.statut.value] += 1

    print("\nBilan par magasin (nombre de recherches) :")
    for magasin in magasins:
        compte = bilan[magasin.id]
        details = ", ".join(f"{cle} {n}" for cle, n in sorted(compte.items()))
        print(f"  - {magasin.nom} : {details or 'rien'}")
    reels = sum(n for c in bilan.values() for cle, n in c.items() if cle in ("api", "collecte"))
    secours = sum(
        n for c in bilan.values() for cle, n in c.items() if cle in ("open_prices", "cache")
    )
    print(f"\n{reels} prix réels mis en cache, {secours} prix de secours (Open Prices, cache).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Préchauffe le cache des prix pour la démo.")
    parseur.add_argument(
        "fichier",
        type=Path,
        help="une recherche ou un EAN par ligne (ex. data/demo/recherches.txt)",
    )
    parseur.add_argument("--code-postal", required=True, help="code postal de la démo, ex. 35170")
    parseur.add_argument("--verbeux", action="store_true", help="affiche le détail des replis")
    args = parseur.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbeux else logging.WARNING)

    recherches = lire_recherches(args.fichier)
    print(f"{len(recherches)} recherches lues pour le code postal {args.code_postal}.")
    return asyncio.run(prechauffer(recherches, args.code_postal, Reglages()))


if __name__ == "__main__":
    sys.exit(main())
