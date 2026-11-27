"""Projection des observations Edge dans les lignes de comparaison du panier."""

import asyncio
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from time import monotonic

from app.collecte.equivalence import choisir_equivalent
from app.config import Reglages
from app.contrats import LigneListe, ModeLigne, Prix, Produit, ResultatLigne, StatutPrix, TypeSource
from app.drives.modeles import DriveId, Recherche, date_tri, ean_valide, normaliser
from app.drives.navigateur import reveiller_edge
from app.drives.service import rechercher_pour_panier

INTERVALLE_S = 2
ATTENTE_CONNEXION_S = 35
MESSAGES = {
    "mauvais_drive": "Le point de retrait actif dans Edge est incorrect.",
    "page_inattendue": "La page marchande n’a pas permis de confirmer le résultat.",
    "reseau": "Erreur de connexion au site marchand.",
    "delai": "Le relevé a expiré.",
    "403": "Le site marchand a refusé l’accès.",
    "429": "Le site marchand a limité les requêtes.",
    "defi": "Le site marchand demande une vérification.",
    "404": "La page de recherche est introuvable.",
}


def _prix(drive: DriveId, observation: dict) -> Prix:
    releve = observation["releve_le"]
    prix_unitaire = observation["prix_par_unite_eur"]
    ancien = observation["ancien"]
    return Prix(
        magasin_id=drive,
        produit=Produit(
            ean=observation["ean"] or None,
            libelle=observation["produit"],
            marque=observation["marque"] or None,
            quantite=observation["format"] or None,
        ),
        prix_centimes=observation["prix_centimes"],
        prix_unitaire_centimes=round(Decimal(prix_unitaire) * 100)
        if prix_unitaire is not None
        else None,
        unite=observation["unite"] or None,
        source=TypeSource.CACHE if ancien else TypeSource.COLLECTE,
        source_detail=("Dernier prix connu · " if ancien else "") + observation["source"],
        releve_le=datetime.fromisoformat(date_tri(releve)),
        date_releve_source=date.fromisoformat(releve) if len(releve) == 10 else None,
        conditions_affichees=observation["promos"],
    )


def _resultat(ligne: LigneListe, drive: DriveId, vue: dict, *, hors_ligne: bool) -> ResultatLigne:
    offres = [_prix(drive, o) for o in vue["produits"]]
    prix = offres[0] if offres and ligne.mode == ModeLigne.PRODUIT else choisir_equivalent(offres)
    etat = vue["etat"]
    remarque = None
    if hors_ligne:
        remarque = "L’extension de collecte Edge ne répond pas. Vérifiez sa configuration initiale."
    elif etat == "attente":
        remarque = "Relevé en attente." if vue["connecte"] else "En attente de l’extension Edge."
    elif etat == "differe":
        remarque = "Relevé encore en file. Relancez la comparaison pour actualiser les prix."
    elif etat == "cours":
        remarque = "Relevé en cours dans Edge."
    elif etat == "pause":
        remarque = "Collecte en pause. " + MESSAGES.get(vue["erreur"], "Réessayez plus tard.")
    elif etat == "echec":
        remarque = MESSAGES.get(vue["erreur"], "Le relevé a échoué.")
    elif etat == "indisponible":
        remarque = "Collecte Edge indisponible."
    elif etat == "sans_correspondance":
        remarque = "Aucun produit correspondant parmi les résultats relevés."
    elif etat == "vide":
        remarque = "Aucun produit trouvé lors du dernier relevé."

    if etat in ("attente", "cours", "differe") and not hors_ligne:
        statut = StatutPrix.EN_ATTENTE
    elif prix:
        statut = StatutPrix.TROUVE
    elif etat == "vide":
        statut = StatutPrix.INTROUVABLE
    else:
        statut = StatutPrix.INDISPONIBLE
    return ResultatLigne(
        ligne_id=ligne.id, magasin_id=drive, statut=statut, prix=prix, remarque=remarque
    )


async def relever_ligne(
    reglages: Reglages, drive: DriveId, ligne: LigneListe, *, suivre: bool
) -> AsyncIterator[ResultatLigne]:
    exact = ligne.mode == ModeLigne.PRODUIT
    q = (ligne.ean or "") if exact else ligne.recherche
    if not normaliser(q) or (exact and not ean_valide(q)):
        yield ResultatLigne(
            ligne_id=ligne.id,
            magasin_id=drive,
            statut=StatutPrix.INDISPONIBLE,
            remarque="EAN invalide." if exact else "Recherche vide.",
        )
        return
    recherche = Recherche(q=q, drives=[drive])
    terme = " ".join(ligne.libelle.split())[:160]
    terme_marchand = terme if exact and any(c.isalpha() for c in terme) else None
    deconnecte_depuis = None
    echeance = monotonic() + reglages.drives_attente_s
    precedent = None
    creer = suivre
    while True:
        vue = await asyncio.to_thread(
            rechercher_pour_panier,
            reglages,
            drive,
            recherche,
            creer=creer,
            terme_marchand=terme_marchand,
        )
        creer = False
        hors_ligne = False
        if suivre and vue["tache_id"] and not vue["connecte"]:
            if deconnecte_depuis is None:
                deconnecte_depuis = monotonic()
                if reglages.drives_demarrer_edge and not reglages.site_partage_origine:
                    await asyncio.to_thread(reveiller_edge)
            hors_ligne = monotonic() - deconnecte_depuis >= ATTENTE_CONNEXION_S
        else:
            deconnecte_depuis = None
        if suivre and precedent and vue["tache_id"]:
            delai_depasse = monotonic() >= echeance
            if reglages.site_partage_origine and (delai_depasse or hors_ligne):
                vue.update(etat="differe", tache_id=None)
                hors_ligne = False
            elif delai_depasse and not hors_ligne:
                vue.update(etat="echec", erreur="delai", tache_id=None)
        resultat = _resultat(ligne, drive, vue, hors_ligne=hors_ligne)
        if resultat != precedent:
            yield resultat
            precedent = resultat
        if not suivre or not vue["tache_id"] or hors_ligne:
            return
        await asyncio.sleep(min(INTERVALLE_S, max(0.0, echeance - monotonic())))
