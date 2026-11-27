"""Lancement du site privé derrière Tailscale Serve, avec sa propre base."""

import argparse
import json
import secrets
from pathlib import Path

import uvicorn

from app.config import RACINE, Reglages
from app.main import creer_app

CONFIGURATION = RACINE / ".env.partage"
PORT = 8001


def preparer(configuration: Path, origine: str) -> Reglages:
    if not configuration.exists():
        valeurs = {
            "SITE_PARTAGE_ORIGINE": origine,
            "SITE_PARTAGE_COMPTES": json.dumps(
                {nom: secrets.token_urlsafe(32) for nom in ("raphael", "adam")}
            ),
            "DRIVES_COLLECTEURS": json.dumps(
                {nom: secrets.token_urlsafe(32) for nom in ("edge-raphael", "edge-adam")}
            ),
            "SECRET_KEY": secrets.token_urlsafe(48),
            "DB_PATH": "data/partage/app.db",
            "DRIVES_DEMARRER_EDGE": "false",
        }
        Reglages(
            _env_file=None,
            site_partage_origine=origine,
            secret_key=valeurs["SECRET_KEY"],
            site_partage_comptes=json.loads(valeurs["SITE_PARTAGE_COMPTES"]),
            drives_collecteurs=json.loads(valeurs["DRIVES_COLLECTEURS"]),
        )
        with configuration.open("x", encoding="utf-8") as fichier:
            fichier.writelines(f"{cle}={valeur}\n" for cle, valeur in valeurs.items())
    reglages = Reglages(_env_file=configuration)
    if reglages.site_partage_origine != origine:
        raise ValueError("Mettez à jour SITE_PARTAGE_ORIGINE dans .env.partage pour cette adresse.")
    return reglages


def main() -> None:
    parser = argparse.ArgumentParser(description="Démarrer le comparateur partagé.")
    parser.add_argument("origine", help="Adresse HTTPS affichée par Tailscale Serve")
    args = parser.parse_args()
    try:
        reglages = preparer(CONFIGURATION, args.origine.rstrip("/"))
    except ValueError as erreur:
        parser.error(str(erreur))
    uvicorn.run(
        creer_app(reglages),
        host="127.0.0.1",
        port=PORT,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )


if __name__ == "__main__":
    main()
