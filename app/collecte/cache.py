"""Cache SQLite des prix collectés (lot 4). BOUCHON : rien n'est encore lu ni écrit.

Clé : enseigne + magasin + recherche. Durée de validité : CACHE_TTL_MIN. Table : schema.sql.
- `lire_frais` : prix encore valide → évite la requête à la source.
- `lire_dernier` : dernier prix connu, même périmé → premier niveau du repli (affiché avec sa date).
- `ecrire` : enregistre un prix réel (jamais de données fictives).
"""

from app.config import Reglages
from app.contrats import Enseigne, LigneListe, ModeLigne, Prix


def cle_recherche(ligne: LigneListe) -> str:
    if ligne.mode == ModeLigne.PRODUIT and ligne.ean:
        return f"ean:{ligne.ean}"
    return f"texte:{' '.join(ligne.recherche.lower().split())}"


def lire_frais(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str) -> Prix | None:
    return None  # lot 4


def lire_dernier(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str) -> Prix | None:
    return None  # lot 4


def ecrire(reglages: Reglages, enseigne: Enseigne, magasin_id: str, cle: str, prix: Prix) -> None:
    return None  # lot 4
