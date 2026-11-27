"""Magasins : liste OpenStreetMap, choix du rayon, géocodage d'une position GPS. Sans réseau."""

import pytest

from app.contrats import Enseigne, Magasin, Position
from app.magasins import geocodage, service
from app.magasins.import_osm import compacter, enseigne_de

BRUZ = Position(lat=48.02516, lon=-1.748362)


def test_enseigne_selon_la_marque_osm():
    assert enseigne_de("Carrefour City") == Enseigne.CARREFOUR
    assert enseigne_de("Intermarché Super") == Enseigne.INTERMARCHE
    assert enseigne_de("Centre Commercial E. Leclerc") == Enseigne.LECLERC
    assert enseigne_de("U Express") == Enseigne.COURSES_U
    assert enseigne_de("Utile") == Enseigne.COURSES_U
    assert enseigne_de("Aldi") is None


def test_compacter_garde_les_4_enseignes_et_le_centre_des_batiments():
    elements = [
        {"type": "node", "id": 1, "lat": 48.0, "lon": -1.7,
         "tags": {"brand": "Intermarché", "name": "Intermarché", "addr:city": "Bruz"}},
        {"type": "way", "id": 2, "center": {"lat": 48.1, "lon": -1.6},
         "tags": {"brand": "Super U", "addr:housenumber": "12", "addr:street": "Place de Bretagne"}},
        {"type": "node", "id": 3, "lat": 48.0, "lon": -1.7, "tags": {"brand": "Aldi"}},
    ]  # fmt: skip
    magasins = compacter(elements)
    assert [m["id"] for m in magasins] == ["n1", "w2"]
    assert magasins[1]["nom"] == "Super U"
    assert magasins[1]["adresse"] == "12 Place de Bretagne"


def _magasin(enseigne: Enseigne, numero: int, km_au_nord: float) -> Magasin:
    return Magasin(
        id=f"{enseigne.value}-osmn{numero}",
        enseigne=enseigne,
        id_enseigne=f"osmn{numero}",
        nom=f"{enseigne.nom} {numero}",
        position=Position(lat=BRUZ.lat + km_au_nord / 111.2, lon=BRUZ.lon),
    )


@pytest.fixture
def osm(reglages, monkeypatch, tmp_path):
    fichier = tmp_path / "osm.json"
    fichier.write_text("[]")
    monkeypatch.setattr(service, "FICHIER_OSM", fichier)
    faux = {e: [_magasin(e, i, km) for i, km in enumerate((1, 3, 8, 15, 40))] for e in Enseigne}
    monkeypatch.setattr(service, "magasins_osm", lambda: faux)
    reglages.magasins_osm = True
    return reglages


@pytest.mark.anyio
async def test_les_plus_proches_de_chaque_enseigne(osm):
    reponse = await service.magasins_proches("35170", osm)
    assert len(reponse.magasins) == 4 * osm.max_magasins_par_enseigne
    assert max(m.distance_km for m in reponse.magasins) == pytest.approx(3, abs=0.1)
    assert reponse.rayon_km is None


@pytest.mark.anyio
async def test_rayon_choisi(osm):
    reponse = await service.magasins_proches("35170", osm, rayon_km=10)
    assert len(reponse.magasins) == 4 * 3  # 1, 3 et 8 km
    assert all(m.distance_km <= 10 for m in reponse.magasins)
    distances = [m.distance_km for m in reponse.magasins]
    assert distances == sorted(distances)


@pytest.mark.anyio
async def test_position_du_navigateur(reglages, monkeypatch):
    async def sans_reseau(*args):
        return []

    monkeypatch.setattr(geocodage, "_api_adresse", sans_reseau)
    ville, position = await geocodage.geocoder("48.02516,-1.74836", reglages)
    assert (ville, position.lat, position.lon) == ("votre position", 48.02516, -1.74836)
    with pytest.raises(geocodage.CodePostalInvalide):
        await geocodage.geocoder("123", reglages)


def test_page_magasins_avec_rayon(client):
    page = client.get("/magasins", params={"code_postal": "35170", "rayon_km": "5"})
    assert page.status_code == 200
    assert "moins de 5 km" in page.text
    assert 'class="badge-trajet"' not in page.text


@pytest.mark.parametrize(
    ("mode", "rayon"), [("voiture", "15"), ("transport", "6"), ("velo", "3"), ("pied", "1,5")]
)
def test_trajet_rayon_du_mode_et_badge_de_proximite(client, mode, rayon):
    params = {"code_postal": "35170", "trajet": "true", "mode_trajet": mode}
    page = client.get("/magasins", params=params)
    assert f"moins de {rayon} km" in page.text
    perso = client.get("/magasins", params={**params, "rayon_trajet": "10.5"})
    assert "moins de 10,5 km" in perso.text
    assert 'class="badge-trajet"' in perso.text
    assert "≈ " in perso.text
