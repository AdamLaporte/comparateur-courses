"""Fixtures communes. Aucun test n'appelle le réseau : toutes les enseignes sont fictives,
et le code postal 35170 est dans la table intégrée du géocodage."""

import pytest
from fastapi.testclient import TestClient

from app.config import Reglages
from app.main import creer_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def reglages(tmp_path) -> Reglages:
    return Reglages(
        _env_file=None,  # ignore le .env local
        db_path=tmp_path / "test.db",
        secret_key="secret-de-test",
        delai_fictif_max_s=0,
        source_carrefour="fictive",
        source_intermarche="fictive",
        source_coursesu="fictive",
        source_leclerc="fictive",
        intermarche_api_key="",
        magasins_osm=False,  # magasins fictifs : pas de fichier OSM à charger dans les tests
        source_produits="fictive",  # pas d'appel à Open Food Facts
        open_prices_actif=False,  # pas d'appel à Open Prices
    )


@pytest.fixture
def client(reglages):
    with TestClient(creer_app(reglages)) as client:
        yield client
