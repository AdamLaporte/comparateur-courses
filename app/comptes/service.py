"""Comptes (facultatifs) : inscription, connexion, mot de passe perdu.

- Mots de passe hachés en argon2 avec pwdlib, jamais stockés ni journalisés en clair.
- La connexion pose `request.session["utilisateur_id"]` (utilisé par app/panier/service.py) ; la liste
  faite sans compte est alors rattachée au compte (`rattacher_liste`).
- Mot de passe perdu : lien signé (itsdangerous), valable DUREE_LIEN_S secondes et à usage unique (il
  contient une empreinte du hachage actuel, qui change dès que le mot de passe change). Envoyé par SMTP si
  SMTP_HOTE est réglé, sinon écrit dans le journal du serveur (développement et démo).
- Trop d'échecs de connexion pour un e-mail : blocage temporaire (MAX_ECHECS en FENETRE_ECHECS_S).
- Articles favoris : un produit précis (EAN) ou une recherche « le moins cher », sans doublon.
- Maison : un code postal enregistré (table adresse_favorite, libellé « Maison »), proposé en un clic sur
  l'accueil et utilisé comme code postal par défaut à la connexion.
Tables : schema.sql. La cagnotte est gérée dans cagnotte.py.
"""

import asyncio
import hashlib
import logging
import re
import smtplib
import sqlite3
import time
from email.message import EmailMessage

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash

from app import db
from app.config import Reglages
from app.magasins.geocodage import CodePostalInconnu, CodePostalInvalide, geocoder

logger = logging.getLogger(__name__)

MOT_DE_PASSE_MIN = 8
MOT_DE_PASSE_MAX = 128
DUREE_LIEN_S = 3600
MAX_ECHECS = 5
FENETRE_ECHECS_S = 15 * 60
MOTIF_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

hacheur = PasswordHash.recommended()
_HACHAGE_FACTICE = hacheur.hash(
    "mot-de-passe-factice"
)  # même durée de calcul si l'e-mail est inconnu
_echecs: dict[str, list[float]] = {}


class ErreurCompte(Exception):
    """Message court, affichable tel quel à l'utilisateur."""


def normaliser_email(email: str) -> str:
    return email.strip().lower()


def verifier_mot_de_passe(mot_de_passe: str) -> None:
    if len(mot_de_passe) < MOT_DE_PASSE_MIN:
        raise ErreurCompte(f"Le mot de passe doit faire au moins {MOT_DE_PASSE_MIN} caractères.")
    if len(mot_de_passe) > MOT_DE_PASSE_MAX:
        raise ErreurCompte(f"Le mot de passe doit faire au plus {MOT_DE_PASSE_MAX} caractères.")


def _par_email(reglages: Reglages, email: str) -> sqlite3.Row | None:
    with db.connexion(reglages.db_path) as cnx:
        return cnx.execute(
            "SELECT id, email, mot_de_passe_hash FROM utilisateur WHERE email = ?", (email,)
        ).fetchone()


def _par_id(reglages: Reglages, utilisateur_id: int) -> sqlite3.Row | None:
    with db.connexion(reglages.db_path) as cnx:
        return cnx.execute(
            "SELECT id, email, mot_de_passe_hash FROM utilisateur WHERE id = ?", (utilisateur_id,)
        ).fetchone()


def email_utilisateur(reglages: Reglages, utilisateur_id: int) -> str | None:
    ligne = _par_id(reglages, utilisateur_id)
    return ligne["email"] if ligne else None


def creer_compte(reglages: Reglages, email: str, mot_de_passe: str) -> int:
    email = normaliser_email(email)
    if not MOTIF_EMAIL.match(email) or len(email) > 254:
        raise ErreurCompte("Adresse e-mail invalide.")
    verifier_mot_de_passe(mot_de_passe)
    try:
        with db.connexion(reglages.db_path) as cnx:
            curseur = cnx.execute(
                "INSERT INTO utilisateur (email, mot_de_passe_hash) VALUES (?, ?)",
                (email, hacheur.hash(mot_de_passe)),
            )
            return curseur.lastrowid
    except sqlite3.IntegrityError as erreur:
        raise ErreurCompte("Un compte existe déjà avec cette adresse e-mail.") from erreur


def _trop_d_echecs(email: str) -> bool:
    limite = time.monotonic() - FENETRE_ECHECS_S
    recents = [t for t in _echecs.get(email, []) if t > limite]
    _echecs[email] = recents
    return len(recents) >= MAX_ECHECS


def authentifier(reglages: Reglages, email: str, mot_de_passe: str) -> int:
    """Identifiant de l'utilisateur si l'e-mail et le mot de passe sont bons, sinon ErreurCompte."""
    email = normaliser_email(email)
    if _trop_d_echecs(email):
        raise ErreurCompte("Trop d'essais. Réessayez dans quelques minutes.")
    ligne = _par_email(reglages, email)
    hachage = ligne["mot_de_passe_hash"] if ligne else _HACHAGE_FACTICE
    valide, nouveau_hachage = hacheur.verify_and_update(mot_de_passe, hachage)
    if ligne is None or not valide:
        _echecs.setdefault(email, []).append(time.monotonic())
        raise ErreurCompte("E-mail ou mot de passe incorrect.")
    _echecs.pop(email, None)
    if nouveau_hachage:  # paramètres d'argon2 renforcés depuis la création du compte
        _enregistrer_hachage(reglages, ligne["id"], nouveau_hachage)
    return ligne["id"]


def _enregistrer_hachage(reglages: Reglages, utilisateur_id: int, hachage: str) -> None:
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "UPDATE utilisateur SET mot_de_passe_hash = ? WHERE id = ?", (hachage, utilisateur_id)
        )


def changer_mot_de_passe(
    reglages: Reglages, utilisateur_id: int, actuel: str, nouveau: str
) -> None:
    ligne = _par_id(reglages, utilisateur_id)
    if ligne is None or not hacheur.verify(actuel, ligne["mot_de_passe_hash"]):
        raise ErreurCompte("Mot de passe actuel incorrect.")
    verifier_mot_de_passe(nouveau)
    _enregistrer_hachage(reglages, utilisateur_id, hacheur.hash(nouveau))


def rattacher_liste(reglages: Reglages, sid: str | None, utilisateur_id: int) -> None:
    """À la connexion : les lignes de la liste faite sans compte passent dans celle du compte."""
    if not sid:
        return
    session = f"session:{sid}"
    compte = f"utilisateur:{utilisateur_id}"
    with db.connexion(reglages.db_path) as cnx:
        destination = compte
        if cnx.execute("SELECT 1 FROM liste_courses WHERE cle = ?", (session,)).fetchone():
            destination = f"liste:{sid}"
            cnx.execute("UPDATE liste_courses SET cle = ? WHERE cle = ?", (destination, session))
        cnx.execute(
            "UPDATE ligne_liste SET proprietaire = ? WHERE proprietaire = ?",
            (destination, session),
        )
        cnx.execute(
            "UPDATE liste_courses SET proprietaire = ? WHERE proprietaire = ?", (compte, session)
        )


# --- Mot de passe perdu ---


def _empreinte(hachage: str) -> str:
    """Change dès que le mot de passe change ; ne révèle rien du hachage (le jeton est lisible)."""
    return hashlib.sha256(hachage.encode()).hexdigest()[:16]


def _signataire(reglages: Reglages) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(reglages.secret_key, salt="reinitialisation-mot-de-passe")


def creer_jeton(reglages: Reglages, utilisateur_id: int) -> str | None:
    ligne = _par_id(reglages, utilisateur_id)
    if ligne is None:
        return None
    return _signataire(reglages).dumps(
        {"id": ligne["id"], "h": _empreinte(ligne["mot_de_passe_hash"])}
    )


def lire_jeton(reglages: Reglages, jeton: str) -> int:
    """Identifiant de l'utilisateur du lien, ou ErreurCompte si le lien est invalide, expiré ou déjà utilisé."""
    try:
        contenu = _signataire(reglages).loads(jeton, max_age=DUREE_LIEN_S)
        ligne = _par_id(reglages, int(contenu["id"]))
    except SignatureExpired as erreur:
        raise ErreurCompte("Ce lien a expiré. Demandez-en un nouveau.") from erreur
    except (BadSignature, KeyError, TypeError, ValueError) as erreur:
        raise ErreurCompte("Ce lien n'est pas valide. Demandez-en un nouveau.") from erreur
    if ligne is None or _empreinte(ligne["mot_de_passe_hash"]) != contenu.get("h"):
        raise ErreurCompte("Ce lien a déjà servi. Demandez-en un nouveau.")
    return ligne["id"]


def reinitialiser(reglages: Reglages, jeton: str, nouveau: str) -> int:
    utilisateur_id = lire_jeton(reglages, jeton)
    verifier_mot_de_passe(nouveau)
    _enregistrer_hachage(reglages, utilisateur_id, hacheur.hash(nouveau))
    _echecs.pop(email_utilisateur(reglages, utilisateur_id) or "", None)
    return utilisateur_id


def _envoyer_smtp(reglages: Reglages, destinataire: str, sujet: str, texte: str) -> None:
    message = EmailMessage()
    message["From"] = reglages.smtp_expediteur or reglages.smtp_utilisateur
    message["To"] = destinataire
    message["Subject"] = sujet
    message.set_content(texte)
    with smtplib.SMTP(reglages.smtp_hote, reglages.smtp_port, timeout=10) as serveur:
        serveur.starttls()
        if reglages.smtp_utilisateur:
            serveur.login(reglages.smtp_utilisateur, reglages.smtp_mot_de_passe)
        serveur.send_message(message)


async def envoyer_lien(reglages: Reglages, email: str, lien: str) -> None:
    """Envoie le lien de réinitialisation. Sans SMTP réglé, l'écrit dans le journal du serveur."""
    texte = (
        "Bonjour,\n\nPour choisir un nouveau mot de passe, ouvrez ce lien (valable une heure) :\n"
        f"{lien}\n\nSi vous n'avez rien demandé, ignorez ce message.\n"
    )
    if not reglages.smtp_hote:
        logger.warning("SMTP non réglé : lien de réinitialisation pour %s : %s", email, lien)
        return
    try:
        await asyncio.to_thread(
            _envoyer_smtp, reglages, email, "GrignotePrix : mot de passe", texte
        )
    except (OSError, smtplib.SMTPException):
        logger.exception("Envoi de l'e-mail de réinitialisation impossible")


async def demander_reinitialisation(reglages: Reglages, email: str, base_url: str) -> None:
    """Envoie un lien si le compte existe. Ne dit jamais à l'utilisateur si l'e-mail est connu."""
    ligne = _par_email(reglages, normaliser_email(email))
    if ligne is None:
        return
    jeton = creer_jeton(reglages, ligne["id"])
    await envoyer_lien(reglages, ligne["email"], f"{base_url}comptes/reinitialiser?jeton={jeton}")


# --- Articles favoris ---

MAX_FAVORIS = 100


def lister_favoris(reglages: Reglages, utilisateur_id: int) -> list[dict]:
    with db.connexion(reglages.db_path) as cnx:
        lignes = cnx.execute(
            "SELECT id, mode, ean, recherche, libelle FROM article_favori "
            "WHERE utilisateur_id = ? ORDER BY libelle COLLATE NOCASE",
            (utilisateur_id,),
        ).fetchall()
    return [dict(ligne) for ligne in lignes]


def ajouter_favori(
    reglages: Reglages,
    utilisateur_id: int,
    mode: str,
    ean: str | None,
    recherche: str,
    libelle: str,
) -> None:
    """Ajoute un favori, sauf s'il existe déjà (même EAN, ou même recherche en mode « équivalent »)."""
    if mode not in ("produit", "equivalent") or (mode == "produit" and not ean):
        raise ErreurCompte("Favori invalide.")
    recherche = " ".join(recherche.split())[:120]
    libelle = " ".join((libelle or recherche).split())[:200]
    favoris = lister_favoris(reglages, utilisateur_id)
    for favori in favoris:
        if mode == "produit" and favori["mode"] == "produit" and favori["ean"] == ean:
            return
        if (
            mode == "equivalent"
            and favori["mode"] == "equivalent"
            and favori["recherche"].lower() == recherche.lower()
        ):
            return
    if len(favoris) >= MAX_FAVORIS:
        raise ErreurCompte(f"{MAX_FAVORIS} favoris au plus.")
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "INSERT INTO article_favori (utilisateur_id, mode, ean, recherche, libelle) "
            "VALUES (?, ?, ?, ?, ?)",
            (utilisateur_id, mode, ean if mode == "produit" else None, recherche, libelle),
        )


def supprimer_favori(reglages: Reglages, utilisateur_id: int, favori_id: int) -> None:
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "DELETE FROM article_favori WHERE id = ? AND utilisateur_id = ?",
            (favori_id, utilisateur_id),
        )


def favori(reglages: Reglages, utilisateur_id: int, favori_id: int) -> dict | None:
    with db.connexion(reglages.db_path) as cnx:
        ligne = cnx.execute(
            "SELECT id, mode, ean, recherche, libelle FROM article_favori "
            "WHERE id = ? AND utilisateur_id = ?",
            (favori_id, utilisateur_id),
        ).fetchone()
    return dict(ligne) if ligne else None


# --- Maison (adresse favorite « Maison », comme sur une carte) ---

LIBELLE_MAISON = "Maison"


def maison(reglages: Reglages, utilisateur_id: int) -> dict | None:
    """{"code_postal", "lat", "lon"} de la maison de l'utilisateur, ou None."""
    with db.connexion(reglages.db_path) as cnx:
        ligne = cnx.execute(
            "SELECT code_postal, lat, lon FROM adresse_favorite "
            "WHERE utilisateur_id = ? AND libelle = ? ORDER BY id DESC LIMIT 1",
            (utilisateur_id, LIBELLE_MAISON),
        ).fetchone()
    return dict(ligne) if ligne else None


async def maison_pour_session(reglages: Reglages, utilisateur_id: int) -> dict | None:
    """{"code_postal", "ville"} à garder dans la session (ville retrouvée par le géocodage)."""
    adresse = maison(reglages, utilisateur_id)
    if adresse is None:
        return None
    try:
        ville, _ = await geocoder(adresse["code_postal"], reglages)
    except (CodePostalInvalide, CodePostalInconnu):
        ville = ""
    except Exception:  # géocodage indisponible : on affiche seulement le code postal
        logger.exception("Géocodage de la maison impossible")
        ville = ""
    return {"code_postal": adresse["code_postal"], "ville": ville}


async def enregistrer_maison(reglages: Reglages, utilisateur_id: int, code_postal: str) -> dict:
    """Remplace la maison de l'utilisateur. Rend {"code_postal", "ville"} ou lève ErreurCompte."""
    try:
        ville, position = await geocoder(code_postal, reglages)
    except CodePostalInvalide as erreur:
        raise ErreurCompte("Le code postal doit faire 5 chiffres.") from erreur
    except CodePostalInconnu as erreur:
        raise ErreurCompte("Ce code postal est introuvable pour l'instant.") from erreur
    code_postal = code_postal.strip()
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "DELETE FROM adresse_favorite WHERE utilisateur_id = ? AND libelle = ?",
            (utilisateur_id, LIBELLE_MAISON),
        )
        cnx.execute(
            "INSERT INTO adresse_favorite (utilisateur_id, libelle, code_postal, lat, lon) "
            "VALUES (?, ?, ?, ?, ?)",
            (utilisateur_id, LIBELLE_MAISON, code_postal, position.lat, position.lon),
        )
    return {"code_postal": code_postal, "ville": ville}


def supprimer_maison(reglages: Reglages, utilisateur_id: int) -> None:
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "DELETE FROM adresse_favorite WHERE utilisateur_id = ? AND libelle = ?",
            (utilisateur_id, LIBELLE_MAISON),
        )
