"""Projection des observations Edge dans les lignes de comparaison du panier."""

import asyncio
import html
import re
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from time import monotonic

from app.collecte.equivalence import choisir_equivalent
from app.config import Reglages
from app.contrats import LigneListe, ModeLigne, Prix, Produit, ResultatLigne, StatutPrix, TypeSource
from app.drives.modeles import (
    DriveId,
    Recherche,
    date_tri,
    ean_valide,
    normaliser,
    terme_simplifie,
)
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


CAMPAGNE = re.compile(
    r"\d+\s*%|\d+\s*€|offert|gratuit|remise|\d+\s*(?:e|è|ème|eme)\b|lot|carte", re.I
)


def nettoyer_promo(texte: str) -> str:
    """Texte de promo d'un drive, lisible : sans HTML et sans le code interne de la campagne.

    « TRAFIC S47-48 - LOT 2 RDG NUTELLA 1 - Le 2 ème à -50% en remise immédiate <br><i>pour un retrait
    jusqu'au 29/11</i> » → « Le 2 ème à -50% en remise immédiate · pour un retrait jusqu'au 29/11 »."""
    texte = re.sub(r"<br\s*/?>", " · ", texte or "", flags=re.I)
    texte = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", texte)).split())
    morceaux = [m.strip() for m in re.split(r"\s+-\s+", texte) if m.strip()]
    # Le code de campagne (« TRAFIC S47-48 », « LOT 2 RDG NUTELLA 1 ») précède le texte client :
    # on garde à partir du dernier morceau qui parle d'une remise.
    utiles = [i for i, m in enumerate(morceaux) if CAMPAGNE.search(m) and not m.isupper()]
    if len(morceaux) > 1 and utiles:
        texte = " - ".join(morceaux[utiles[-1] :])
    return texte.strip(" ·")


def _meme_produit_par_nom(reglages: Reglages, drive: DriveId, ligne: LigneListe) -> dict | None:
    """Produit précis dont le code-barres n'est pas celui du drive (plusieurs EAN existent pour un même
    produit) : même nom et même format parmi les relevés déjà faits, sans lancer de nouveau relevé."""
    texte = " ".join((ligne.recherche or ligne.libelle).split())[:160]
    if not normaliser(texte):
        return None
    vue = rechercher_pour_panier(
        reglages, drive, Recherche(q=texte, drives=[drive]), creer=False, terme_marchand=None
    )
    format_voulu = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|cl|ml)\b", ligne.libelle.lower())
    if not format_voulu:  # sans format, trop risqué : on garde « aucun produit correspondant »
        return None
    voulu = format_voulu[1].replace(",", ".") + format_voulu[2]
    for produit in vue["produits"]:
        texte_produit = normaliser(f"{produit['produit']} {produit['format']}").replace(" ", "")
        if ean_valide(produit.get("ean") or "") and voulu in texte_produit:
            return {**produit, "source": f"{produit['source']} · même produit, autre code-barres"}
    return None


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
        conditions_affichees=nettoyer_promo(observation["promos"]),
    )


def _choisir_concordant(ligne: LigneListe, produits: list[dict], offres: list[Prix]) -> Prix | None:
    """« Le moins cher » d'une recherche simplifiée (« carré frais ») : parmi les résultats qui contiennent
    tous les mots du produit — et le bon format s'il est donné (« 200 g ») —, le moins cher ; sinon le
    premier résultat du drive."""
    if not offres:
        return None
    mots = normaliser(terme_simplifie(ligne.recherche)).split()

    def contient(produit: dict) -> bool:
        texte = normaliser(f"{produit['produit']} {produit['marque']} {produit['format']}").split()
        return all(any(t.startswith(m.rstrip("sx") or m) for t in texte) for m in mots)

    concordants = [
        offre for offre, produit in zip(offres, produits, strict=True) if contient(produit)
    ]
    format_voulu = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|gr?|cl|ml|l)\b", ligne.recherche.lower())
    if format_voulu and concordants:
        voulu = format_voulu[1].replace(",", ".") + format_voulu[2].replace("gr", "g")
        au_format = [
            o
            for o in concordants
            if voulu
            in normaliser(f"{o.produit.libelle} {o.produit.quantite or ''}").replace(" ", "")
        ]
        concordants = au_format or concordants
    return choisir_equivalent(concordants) if concordants else offres[0]


def _resultat(ligne: LigneListe, drive: DriveId, vue: dict, *, hors_ligne: bool) -> ResultatLigne:
    offres = [_prix(drive, o) for o in vue["produits"]]
    if ligne.mode == ModeLigne.PRODUIT:
        prix = offres[0] if offres else None
    else:
        prix = _choisir_concordant(ligne, vue["produits"], offres)
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
        if exact and vue["etat"] == "sans_correspondance" and not vue["produits"]:
            secours = await asyncio.to_thread(_meme_produit_par_nom, reglages, drive, ligne)
            if secours:
                vue = {**vue, "etat": "recent", "produits": [secours]}
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
