import json
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from app import db
from app.collecte.equivalence import est_le_sujet
from app.config import Reglages
from app.drives.modeles import (
    DRIVES,
    Depot,
    DriveId,
    EnseigneDrive,
    ProduitObserve,
    Recherche,
    date_tri,
    ean_valide,
    normaliser,
    point_collecteur,
    terme_simplifie,
    url_marchande,
)

LIMITE_RESULTATS = 20
QUANTITE = re.compile(r"\b\d+(?:\.\d+)?(?:ml|cl|l|kg|g)\b")
LOT = re.compile(r"\b(?:pack|lot|[2-9]\d* bouteilles)\b|\b\d+ x (?=\d)")


class BailInvalide(ValueError):
    """La tâche ne peut plus recevoir un relevé de ce collecteur."""


def maintenant() -> datetime:
    return datetime.now(UTC)


def horodater(instant: datetime) -> str:
    return instant.isoformat(timespec="microseconds")


def observer(
    cnx: sqlite3.Connection,
    drive: DriveId,
    produit: ProduitObserve,
    releve_le: str,
    source: str,
) -> int:
    url = url_marchande(drive, produit.url)
    reference = (
        f"ref:{produit.id_produit_source}"
        if produit.id_produit_source
        else f"ean:{produit.ean}"
        if ean_valide(produit.ean)
        else f"url:{url}|{normaliser(produit.produit)}|{normaliser(produit.format)}"
    )
    contenu = produit.model_dump(mode="json", exclude={"prix_eur", "prix_par_unite_eur"})
    contenu.update(
        url=url,
        source=source,
        prix_centimes=int(produit.prix_eur * 100),
        prix_par_unite_eur=(
            format(produit.prix_par_unite_eur.normalize(), "f")
            if produit.prix_par_unite_eur is not None
            else None
        ),
    )
    donnees = json.dumps(contenu, ensure_ascii=False, sort_keys=True)
    date = date_tri(releve_le)
    texte = normaliser(
        " ".join((produit.produit, produit.marque, produit.variante, produit.format))
    )
    cnx.execute("INSERT OR IGNORE INTO drive_reference VALUES (?, ?)", (drive, reference))
    # Un produit relevé sur un drive, avec un vrai code-barres, rejoint le catalogue des produits : la
    # recherche d'articles le propose ensuite. On ne remplace pas une fiche déjà connue.
    if ean_valide(produit.ean):
        cnx.execute(
            "INSERT OR IGNORE INTO produit (ean, libelle, marque, quantite, source, maj_le) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                produit.ean,
                produit.produit,
                produit.marque or None,
                produit.format or None,
                f"drive:{drive}",
                horodater(maintenant()),
            ),
        )
    cnx.execute(
        "INSERT OR IGNORE INTO drive_observation "
        "(drive_id, reference, date_tri, releve_le, texte, ean, contenu)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (drive, reference, date, releve_le, f" {texte} ", produit.ean, donnees),
    )
    return cnx.execute(
        "SELECT id FROM drive_observation "
        "WHERE drive_id = ? AND reference = ? AND date_tri = ? AND contenu = ?",
        (drive, reference, date, donnees),
    ).fetchone()["id"]


def _classer(lignes: list[sqlite3.Row], cle: str, *, alternatives: bool = False) -> list[dict]:
    candidats = []
    mots = set(cle.split())
    requete_formatee = bool(QUANTITE.search(cle))
    lot_demande = bool(LOT.search(cle))
    code_exact = ean_valide(cle)
    for ligne in lignes:
        produit = json.loads(ligne["contenu"])
        nom = normaliser(produit["produit"])
        format_produit = normaliser(produit["format"])
        texte = " ".join(
            (nom, normaliser(produit["marque"]), normaliser(produit["variante"]), format_produit)
        )
        if code_exact:
            if produit["ean"] != cle:
                continue
        elif not alternatives and not mots.issubset(texte.split()):
            continue
        score = (
            len(mots.intersection(texte.split())),
            requete_formatee and lot_demande == bool(LOT.search(f"{nom} {format_produit}")),
            nom == cle,
            cle in texte,
            len(mots.intersection(format_produit.split())),
        )
        produit.update(releve_le=ligne["releve_le"], date_tri=ligne["date_tri"])
        candidats.append((score, produit))
    candidats.sort(key=lambda candidat: candidat[0], reverse=True)
    return [produit for _, produit in candidats]


def _expiration(cnx: sqlite3.Connection, instant: str) -> None:
    cnx.execute(
        "UPDATE drive_tache SET etat='echec', erreur='delai', termine_le=? "
        "WHERE etat IN ('attente','cours') AND expire_le <= ?",
        (instant, instant),
    )


def _vue_drive(
    cnx: sqlite3.Connection,
    reglages: Reglages,
    drive: DriveId,
    recherche: Recherche,
    instant: datetime,
    creer: bool,
    *,
    alternatives: bool = True,
    terme_marchand: str | None = None,
) -> dict:
    horodatage = horodater(instant)
    seuil = horodater(instant - timedelta(minutes=reglages.drives_fraicheur_min))
    tache = cnx.execute(
        "SELECT * FROM drive_tache WHERE drive_id=? AND cle=? ORDER BY id DESC LIMIT 1",
        (drive, recherche.cle),
    ).fetchone()
    collecteur = cnx.execute("SELECT * FROM drive_collecteur WHERE drive_id=?", (drive,)).fetchone()
    pause = bool(
        collecteur and collecteur["pause_jusqua"] and collecteur["pause_jusqua"] > horodatage
    )
    presence_enseigne = cnx.execute(
        "SELECT vu_le FROM drive_collecteur_enseigne WHERE enseigne=?",
        (drive.split("-", 1)[0],),
    ).fetchone()
    seuil_presence = horodater(instant - timedelta(seconds=75))
    connecte = any(
        presence and presence["vu_le"] and presence["vu_le"] > seuil_presence
        for presence in (collecteur, presence_enseigne)
    )
    mots = recherche.cle.split()
    filtre, parametres = (
        ("o.ean=?", [recherche.cle])
        if ean_valide(recherche.cle)
        else (" AND ".join("instr(o.texte, ?) > 0" for _ in mots), [f" {mot} " for mot in mots])
    )
    historique = cnx.execute(
        "SELECT o.* FROM drive_reference r JOIN drive_observation o ON o.id = ("
        "SELECT id FROM drive_observation WHERE drive_id=r.drive_id AND reference=r.cle "
        f"ORDER BY date_tri DESC, id DESC LIMIT 1) WHERE r.drive_id=? AND {filtre} "
        "ORDER BY o.date_tri DESC, o.id DESC",
        (drive, *parametres),
    ).fetchall()
    candidats = _classer(historique, recherche.cle)
    frais = [produit for produit in candidats if seuil <= produit["date_tri"] <= horodatage]
    # « Le moins cher » : un relevé fait pour une autre recherche et qui cite seulement le mot (« pâte à
    # tartiner sans lait » pour « lait ») ne dispense pas d'interroger le drive.
    repond = bool(frais) and (
        alternatives
        or ean_valide(recherche.cle)
        or any(est_le_sujet(p["produit"], p["marque"], recherche.q) for p in frais)
    )
    etat = "indisponible"
    erreur = None
    tache_id = None
    expiree = tache and tache["etat"] in ("attente", "cours") and tache["expire_le"] <= horodatage
    if (
        tache
        and tache["etat"] == "vide"
        and tache["termine_le"] >= horodater(instant - timedelta(minutes=10))
    ):
        etat = "vide"
        frais = []
    elif tache and tache["etat"] == "succes" and tache["termine_le"] >= seuil:
        observes = cnx.execute(
            "SELECT o.* FROM drive_observation o JOIN drive_tache_observation l "
            "ON l.observation_id=o.id WHERE l.tache_id=? ORDER BY o.id",
            (tache["id"],),
        ).fetchall()
        frais = _classer(observes, recherche.cle, alternatives=alternatives) or frais
        etat = "recent" if frais else "sans_correspondance"
    elif repond:
        etat = "recent"
    elif tache and tache["etat"] in ("attente", "cours") and not expiree:
        etat, tache_id = tache["etat"], tache["id"]
    elif pause:
        etat, erreur = "pause", tache["erreur"] if tache and tache["erreur"] else None
    elif creer and reglages.collecte_drives_active:
        duree = timedelta(days=1) if reglages.site_partage_origine else timedelta(minutes=5)
        tache_id = cnx.execute(
            "INSERT INTO drive_tache (drive_id, cle, requete, etat, expire_le) "
            "VALUES (?, ?, ?, 'attente', ?) RETURNING id",
            (
                drive,
                recherche.cle,
                # Le drive ne comprend pas « 200gr*8 0% » : on lui envoie seulement les mots du produit.
                terme_simplifie(terme_marchand or recherche.q) or terme_marchand or recherche.q,
                horodater(instant + duree),
            ),
        ).fetchone()["id"]
        etat = "attente"
    elif tache and tache["etat"] == "echec":
        etat, erreur = "echec", tache["erreur"]
    elif expiree:
        etat, erreur = "echec", "delai"
    produits = frais or candidats
    for produit in produits:
        produit["ancien"] = etat != "recent" or not (seuil <= produit["date_tri"] <= horodatage)
        produit.pop("date_tri")
    return {
        "drive_id": drive,
        "nom": DRIVES[drive].nom,
        "etat": etat,
        "erreur": erreur,
        "tache_id": tache_id,
        "connecte": connecte,
        "produits": produits[:LIMITE_RESULTATS] if alternatives else produits,
    }


def rechercher_pour_panier(
    reglages: Reglages,
    drive: DriveId,
    recherche: Recherche,
    *,
    creer: bool,
    terme_marchand: str | None,
) -> dict:
    instant = maintenant()
    with db.connexion(reglages.db_path) as cnx:
        if creer:
            cnx.execute("BEGIN IMMEDIATE")
            _expiration(cnx, horodater(instant))
        return _vue_drive(
            cnx,
            reglages,
            drive,
            recherche,
            instant,
            creer,
            alternatives=False,
            terme_marchand=terme_marchand,
        )


def rechercher(reglages: Reglages, recherche: Recherche, *, creer: bool) -> list[dict]:
    instant = maintenant()
    with db.connexion(reglages.db_path) as cnx:
        if creer:
            cnx.execute("BEGIN IMMEDIATE")
            _expiration(cnx, horodater(instant))
        resultats = [
            _vue_drive(cnx, reglages, drive, recherche, instant, creer)
            for drive in dict.fromkeys(recherche.drives)
        ]
    groupes = {}
    for resultat in resultats:
        for produit in resultat["produits"]:
            ean = produit["ean"]
            marque, variante, conditionnement = (
                normaliser(produit[c]) for c in ("marque", "variante", "format")
            )
            if not variante and marque and conditionnement:
                exclus = set(marque.split() + conditionnement.split())
                variante = " ".join(
                    mot for mot in normaliser(produit["produit"]).split() if mot not in exclus
                )
            cles = []
            if ean_valide(ean):
                cles.append(("ean", ean))
            if marque and variante and conditionnement:
                cles.append(("champs", marque, variante, conditionnement))
            for cle in cles:
                groupes.setdefault(cle, []).append((resultat["drive_id"], produit))
    for cle, membres in groupes.items():
        if len({drive for drive, _ in membres}) < 2:
            continue
        codes = {p["ean"] for _, p in membres if ean_valide(p["ean"])}
        if cle[0] == "champs" and (len(membres) != 2 or len(codes) > 1):
            continue
        for _, produit in membres:
            produit.setdefault("correspondance", "ean" if cle[0] == "ean" else "possible")
            if cle[0] == "ean":
                produit["correspondance"] = "ean"
    return resultats


def prendre(
    reglages: Reglages,
    drive: DriveId,
    collecteur: str | None = None,
) -> dict | None:
    return _prendre(reglages, (drive,), collecteur)


def prendre_enseigne(
    reglages: Reglages, enseigne: EnseigneDrive, collecteur: str | None
) -> dict | None:
    drives = tuple(d for d in DRIVES if d.startswith(enseigne + "-"))
    return _prendre(reglages, drives, collecteur, enseigne=enseigne)


def _prendre(
    reglages: Reglages,
    drives: tuple[DriveId, ...],
    collecteur: str | None,
    *,
    enseigne: EnseigneDrive | None = None,
) -> dict | None:
    instant = maintenant()
    horodatage = horodater(instant)
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute("BEGIN IMMEDIATE")
        _expiration(cnx, horodatage)
        if enseigne:
            _signaler_enseigne(cnx, enseigne, horodatage)
        else:
            _signaler(cnx, drives[0], horodatage)
        parametres = ", ".join("?" for _ in drives)
        ligne = cnx.execute(
            "UPDATE drive_tache SET etat='cours', bail=?, expire_le=? WHERE id=( "
            f"SELECT t.id FROM drive_tache t WHERE t.drive_id IN ({parametres}) "
            "AND t.etat='attente' "
            "AND NOT EXISTS (SELECT 1 FROM drive_tache b WHERE b.drive_id=t.drive_id AND b.etat='cours') "
            "AND NOT EXISTS (SELECT 1 FROM drive_collecteur c WHERE c.drive_id=t.drive_id "
            "AND c.pause_jusqua > ?) ORDER BY t.id LIMIT 1"
            ") RETURNING id, drive_id, requete, bail",
            (secrets.token_hex(24), horodater(instant + timedelta(minutes=2)), *drives, horodatage),
        ).fetchone()
        if ligne is None:
            return None
        if collecteur:
            cnx.execute("INSERT INTO drive_attribution VALUES (?, ?)", (ligne["id"], collecteur))
        reponse = dict(ligne)
        if enseigne:
            _signaler(cnx, ligne["drive_id"], horodatage)
            drive = ligne["drive_id"]
            reponse["point"] = point_collecteur(drive, DRIVES[drive])
        return reponse


def _signaler_enseigne(cnx: sqlite3.Connection, enseigne: EnseigneDrive, horodatage: str) -> None:
    cnx.execute(
        "INSERT INTO drive_collecteur_enseigne VALUES (?, ?) "
        "ON CONFLICT (enseigne) DO UPDATE SET vu_le=excluded.vu_le",
        (enseigne, horodatage),
    )


def signaler_enseigne(reglages: Reglages, enseigne: EnseigneDrive) -> None:
    with db.connexion(reglages.db_path) as cnx:
        _signaler_enseigne(cnx, enseigne, horodater(maintenant()))


def _signaler(cnx: sqlite3.Connection, drive: DriveId, horodatage: str) -> str | None:
    return cnx.execute(
        "INSERT INTO drive_collecteur (drive_id, vu_le) VALUES (?, ?) "
        "ON CONFLICT (drive_id) DO UPDATE SET vu_le=excluded.vu_le RETURNING pause_jusqua",
        (drive, horodatage),
    ).fetchone()["pause_jusqua"]


def signaler(reglages: Reglages, drive: DriveId) -> None:
    with db.connexion(reglages.db_path) as cnx:
        _signaler(cnx, drive, horodater(maintenant()))


def deposer(reglages: Reglages, tache_id: int, depot: Depot, collecteur: str | None = None) -> None:
    instant = maintenant()
    horodatage = horodater(instant)
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute("BEGIN IMMEDIATE")
        tache = cnx.execute("SELECT * FROM drive_tache WHERE id=?", (tache_id,)).fetchone()
        if not tache or tache["bail"] != depot.bail or tache["drive_id"] != depot.drive_id:
            raise BailInvalide("Bail ou drive incorrect.")
        if collecteur:
            attribution = cnx.execute(
                "SELECT collecteur FROM drive_attribution WHERE tache_id=?", (tache_id,)
            ).fetchone()
            if attribution is None or attribution["collecteur"] != collecteur:
                raise BailInvalide("Ce bail appartient à un autre collecteur.")
        if tache["etat"] not in ("cours", "attente"):
            if tache["erreur"] == "delai" and tache["expire_le"] <= horodatage:
                raise BailInvalide("Bail expiré.")
            return
        if tache["etat"] != "cours" or tache["expire_le"] <= horodatage:
            raise BailInvalide("Bail expiré.")
        etat, erreur = depot.etat, depot.erreur
        if etat != "echec" and depot.service_observe != depot.drive_id.split("-", 1)[1]:
            etat, erreur = "echec", "mauvais_drive"
        if etat == "succes":
            for produit in depot.produits:
                identifiant = observer(cnx, depot.drive_id, produit, horodatage, "Edge")
                cnx.execute(
                    "INSERT OR IGNORE INTO drive_tache_observation VALUES (?, ?)",
                    (tache_id, identifiant),
                )
        if erreur in ("403", "429", "defi"):
            cnx.execute(
                "UPDATE drive_collecteur SET pause_jusqua=? WHERE drive_id=?",
                (horodater(instant + timedelta(minutes=15)), depot.drive_id),
            )
            cnx.execute(
                "UPDATE drive_tache SET etat='echec', erreur=?, termine_le=? "
                "WHERE drive_id=? AND etat='attente'",
                (erreur, horodatage, depot.drive_id),
            )
        cnx.execute(
            "UPDATE drive_tache SET etat=?, erreur=?, termine_le=? WHERE id=?",
            (etat, erreur, horodatage, tache_id),
        )
