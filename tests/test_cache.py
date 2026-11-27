"""Cache SQLite : prix frais, dernier prix connu, jamais de fictif, réponses des services ouverts."""

from datetime import UTC, datetime, timedelta

import pytest

from app import db
from app.collecte import cache, orchestrateur
from app.contrats import (
    Enseigne,
    LigneListe,
    Magasin,
    ModeLigne,
    Position,
    Prix,
    Produit,
    StatutPrix,
    TypeSource,
)
from app.sources.base import SourceIndisponible, SourcePrix

MAGASIN = Magasin(
    id="carrefour-136",
    enseigne=Enseigne.CARREFOUR,
    id_enseigne="136",
    nom="Carrefour Drive Rennes Centre Alma",
    position=Position(lat=48.0877, lon=-1.6741),
)
LIGNE = LigneListe(
    id=1, mode=ModeLigne.PRODUIT, ean="3276554163158", recherche="lait", libelle="Lait"
)
CLE = cache.cle_recherche(LIGNE)


def _prix(source=TypeSource.COLLECTE, est_fictif=False, centimes=105) -> Prix:
    return Prix(
        magasin_id=MAGASIN.id,
        produit=Produit(ean="3276554163158", libelle="Lait demi-écrémé Carrefour Classic'"),
        prix_centimes=centimes,
        source=source,
        source_detail="Carrefour (collecte)",
        releve_le=datetime(2026, 11, 26, 17, 30, tzinfo=UTC),
        est_fictif=est_fictif,
    )


@pytest.fixture
def reglages_db(reglages):
    db.initialiser(reglages.db_path)
    return reglages


def test_cle_recherche():
    assert CLE == "ean:3276554163158"
    ligne = LigneListe(id=2, mode=ModeLigne.EQUIVALENT, recherche="  Lait   Demi ", libelle="x")
    assert cache.cle_recherche(ligne) == "texte:lait demi"


def test_ecrire_puis_lire_frais(reglages_db):
    assert cache.lire_frais(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE) is None
    cache.ecrire(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix())
    lu = cache.lire_frais(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE)
    assert lu == _prix()
    # La clé distingue les magasins.
    assert cache.lire_frais(reglages_db, Enseigne.CARREFOUR, "carrefour-999", CLE) is None


def test_prix_perime_seulement_en_dernier_connu(reglages_db, monkeypatch):
    cache.ecrire(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix())
    plus_tard = datetime.now(UTC) + timedelta(minutes=reglages_db.cache_ttl_min + 1)
    monkeypatch.setattr(cache, "maintenant", lambda: plus_tard)

    assert cache.lire_frais(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE) is None
    dernier = cache.lire_dernier(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE)
    assert dernier is not None
    assert dernier.source == TypeSource.CACHE
    assert dernier.source_detail == "Dernier prix connu (Carrefour (collecte))"
    assert dernier.releve_le == _prix().releve_le  # date du relevé d'origine
    assert dernier.prix_centimes == 105


def test_jamais_de_fictif_ni_de_cache_en_cache(reglages_db):
    cache.ecrire(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix(est_fictif=True))
    cache.ecrire(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix(TypeSource.FICTIVE))
    cache.ecrire(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix(TypeSource.CACHE))
    assert cache.lire_dernier(reglages_db, Enseigne.CARREFOUR, MAGASIN.id, CLE) is None


def test_base_absente_ne_fait_pas_echouer(reglages):
    # Pas de db.initialiser : la table n'existe pas, le cache répond « rien ».
    assert cache.lire_frais(reglages, Enseigne.CARREFOUR, MAGASIN.id, CLE) is None
    cache.ecrire(reglages, Enseigne.CARREFOUR, MAGASIN.id, CLE, _prix())
    assert cache.lire_reponse(reglages, "x", None) is None


def test_reponses_des_services(reglages_db, monkeypatch):
    cache.ecrire_reponse(reglages_db, "open_prices:lieux:rennes", {"items": [1, 2]})
    assert cache.lire_reponse(reglages_db, "open_prices:lieux:rennes", 60) == {"items": [1, 2]}
    plus_tard = datetime.now(UTC) + timedelta(minutes=61)
    monkeypatch.setattr(cache, "maintenant", lambda: plus_tard)
    assert cache.lire_reponse(reglages_db, "open_prices:lieux:rennes", 60) is None
    assert cache.lire_reponse(reglages_db, "open_prices:lieux:rennes", None) == {"items": [1, 2]}


class SourceReelle(SourcePrix):
    """Source « collecte » de test : renvoie un prix, puis tombe en panne."""

    enseigne = Enseigne.CARREFOUR
    type_source = TypeSource.COLLECTE
    nom = "Carrefour (collecte)"

    def __init__(self):
        self.en_panne = False
        self.appels = 0

    async def trouver_magasins(self, position, rayon_km, max_magasins):
        return [MAGASIN]

    async def chercher_produits(self, magasin, recherche, limite=20):
        return []

    async def obtenir_prix(self, magasin, ean):
        self.appels += 1
        if self.en_panne:
            raise SourceIndisponible("403 défi anti-robots")
        return _prix()


@pytest.mark.anyio
async def test_orchestrateur_utilise_le_cache_puis_le_dernier_prix(reglages_db, monkeypatch):
    source = SourceReelle()
    premier = await orchestrateur.resoudre(source, LIGNE, MAGASIN, reglages_db)
    assert premier.statut == StatutPrix.TROUVE and source.appels == 1

    # Prix frais : aucune nouvelle requête.
    deuxieme = await orchestrateur.resoudre(source, LIGNE, MAGASIN, reglages_db)
    assert deuxieme.prix == premier.prix and source.appels == 1

    # Cache périmé et source en panne : dernier prix connu, avec sa date.
    plus_tard = datetime.now(UTC) + timedelta(minutes=reglages_db.cache_ttl_min + 1)
    monkeypatch.setattr(cache, "maintenant", lambda: plus_tard)
    source.en_panne = True
    secours = await orchestrateur.resoudre(source, LIGNE, MAGASIN, reglages_db)
    assert source.appels == 2
    assert secours.statut == StatutPrix.TROUVE
    assert secours.remarque == "Dernier prix connu"
    assert secours.prix.source == TypeSource.CACHE
    assert secours.prix.releve_le == _prix().releve_le
