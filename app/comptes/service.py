"""Comptes (facultatifs) : inscription, connexion, mot de passe perdu.

- Mots de passe hachés en argon2 avec pwdlib, jamais stockés ni journalisés en clair.
- La connexion pose `request.session["utilisateur_id"]` (utilisé par app/panier/service.py) ; la liste
  faite sans compte est alors rattachée au compte (`rattacher_liste`).
- Mot de passe perdu : lien signé (itsdangerous), valable DUREE_LIEN_S secondes et à usage unique (il
  contient une empreinte du hachage actuel, qui change dès que le mot de passe change). Envoyé par SMTP si
  SMTP_HOTE est réglé, sinon écrit dans le journal du serveur (développement et démo).
- Trop d'échecs de connexion pour un e-mail : blocage temporaire (MAX_ECHECS en FENETRE_ECHECS_S).
Tables : schema.sql. Articles favoris, « maison » et cagnotte : à venir.
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
    with db.connexion(reglages.db_path) as cnx:
        cnx.execute(
            "UPDATE ligne_liste SET proprietaire = ? WHERE proprietaire = ?",
            (f"utilisateur:{utilisateur_id}", f"session:{sid}"),
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
            _envoyer_smtp, reglages, email, "Comparateur de courses : mot de passe", texte
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
