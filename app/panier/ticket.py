"""Photo d'un ticket de caisse → articles à ajouter à la liste (mode « le moins cher équivalent »).

Lecture du texte par RapidOCR (modèles ONNX installés avec le paquet : ni réseau, ni clé), puis
analyse des lignes : une ligne d'article finit par un prix, tout s'arrête au « TOTAL ».
"""

import re
from functools import cache

# Lignes avec un prix qui ne sont pas des articles.
_MOTS_IGNORES = re.compile(
    r"total|sous.?total|\bcb\b|carte|esp[eè]ces|rendu|monnaie|\btva\b|remise|r[ée]duction"
    r"|avantage|fid[ée]lit|cagnotte|bon d|ticket|payer|montant|articles?\b",
    re.I,
)
_PRIX_FIN = re.compile(r"^(.*?)\s*(\d+[,.]\d{2})\s*(?:€|eur)?\s*[a-z]?$", re.I)
_QUANTITE = re.compile(r"^(\d{1,2})\s*[x*]\s*\d+[,.]\d{2}", re.I)

# shortcut: abréviations relevées sur des tickets Carrefour, Leclerc, Intermarché et U ; à compléter.
_ABREVIATIONS = [
    (r"\b1/2\s*ecr\w*", "demi-écrémé"),
    (r"\bdemi\s*ecr\w*", "demi-écrémé"),
    (r"\bent\b|\bentier\b", "entier"),
    (r"\becr\b", "écrémé"),
    (r"\blt\b|\blait\w*", "lait"),
    (r"\bfrom\b|\bfrm\b", "fromage"),
    (r"\bjb\b|\bjamb\b", "jambon"),
    (r"\bpdt\b|\bp\.? ?de ?terre\b", "pommes de terre"),
    (r"\byaourt?s?\b|\byt\b|\byaou\b", "yaourt"),
    (r"\bbte\b", "boîte"),
    (r"\bchoc\b|\bchoco\b", "chocolat"),
    (r"\bcafe\b|\bcaf\b", "café"),
    (r"\bcerea?l?\b|\bcerea\w*", "céréales"),
    (r"\bpq\b|\bpap\.? ?toil\w*", "papier toilette"),
    (r"\bbeur\b|\bbeurr?\b", "beurre"),
    (r"\bdx\b", "doux"),
    (r"\bsal\b", "salé"),
    (r"\boeuf\w*|\boeu\b", "oeufs"),
    (r"\bpat\b|\bpates\b", "pâtes"),
    (r"\bspag\w*", "spaghetti"),
    (r"\bsauc\b", "sauce"),
    (r"\btom\b|\btomat\w*", "tomate"),
    (r"\bpoul\b|\bpoulet\w*", "poulet"),
    (r"\bstk\b|\bsteak\w*", "steak"),
    (r"\bhach\w*", "haché"),
    (r"\bcr\.? ?fr\w*|\bcreme ?fr\w*", "crème fraîche"),
    (r"\bfr\b", "frais"),
    (r"\bjus ?d?'? ?or\w*|\bj\.? ?orange\b", "jus d'orange"),
    (r"\beau ?min\w*|\beau ?gaz\w*", "eau"),
    (r"\bbanan\w*", "banane"),
    (r"\bpom\b|\bpomm\b", "pomme"),
    (r"\bcarot\w*", "carotte"),
    (r"\bsal\.? ?verte\b|\bsalad\w*", "salade"),
    (r"\bgrat\w*|\brap\w*", "râpé"),
    (r"\bemment?\w*", "emmental"),
    (r"\bmozza\w*", "mozzarella"),
    (r"\bbisc\b|\bbiscuit\w*", "biscuits"),
    (r"\bconf\b|\bconfit\w*", "confiture"),
    (r"\bhle\b|\bhuile\b", "huile"),
    (r"\bsuc\b|\bsucr\b", "sucre"),
    (r"\bfar\b|\bfarin\w*", "farine"),
    (r"\bchips\w*", "chips"),
    (r"\bpain ?mie\b|\bp\.? ?mie\b", "pain de mie"),
    (r"\bbag\b|\bbaguet\w*", "baguette"),
    (r"\blessiv\w*|\blss\b", "lessive"),
    (r"\bliq\.? ?vais\w*|\bvaiss\w*", "liquide vaisselle"),
    (r"\bdent\w*", "dentifrice"),
    (r"\bshamp\w*", "shampooing"),
]

# Mots connus pour recoller l'OCR qui perd les espaces : « PATESSPAGHETTI » → « pates spaghetti ».
_VOCABULAIRE = set(
    """
    pates pate spaghetti spaghettis penne coquillettes riz lait demi ecreme entier beurre doux
    sale oeufs oeuf plein air fromage emmental rape mozzarella comte camembert yaourt yaourts
    nature fraise vanille chocolat noir lait cafe moulu dosettes the sucre farine huile olive
    tournesol sel poivre sauce tomate tomates pesto ketchup mayonnaise moutarde jambon blanc
    poulet filet steak hache saucisses lardons thon sardines saumon pain mie baguette brioche
    cereales muesli biscuits confiture miel pate tartiner nutella compote pommes pomme banane
    bananes orange oranges citron carottes carotte salade oignons ail courgette poivron
    champignons haricots verts petits pois mais lentilles pizza surgele surgeles frites chips
    eau minerale gazeuse jus soda cola biere vin lessive liquide vaisselle papier toilette
    essuie tout dentifrice shampooing gel douche savon creme fraiche bio uht bouteille brique
    paquet sachet boite lot x stk jb lt ecr pdt pq bte choc
    """.split()  # noqa: SIM905 (plus lisible qu'une liste)
)


@cache
def _moteur():
    from rapidocr_onnxruntime import RapidOCR  # import lent (onnxruntime) : seulement au besoin

    return RapidOCR()


def lire_texte(image: bytes) -> list[str]:
    """Lignes de texte du ticket, de haut en bas. Lent (quelques secondes) : à lancer hors boucle."""
    boites, _ = _moteur()(image)
    if not boites:
        return []
    # Une boîte = 4 coins (haut-gauche, haut-droit, bas-droit, bas-gauche) + texte. Sur une photo
    # penchée, le prix à droite est plus haut que son libellé : on prolonge la pente de la boîte
    # de début de ligne pour savoir si une autre boîte est sur la même ligne.
    lignes: list[list] = []
    for boite in sorted(boites, key=lambda b: b[0][0][0]):
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = boite[0]
        milieu_x, milieu_y, hauteur = (x1 + x2 + x3 + x4) / 4, (y1 + y2 + y3 + y4) / 4, y4 - y1
        for ligne in lignes:
            pente, x0, y0 = ligne[0]
            if abs(y0 + pente * (milieu_x - x0) - milieu_y) < hauteur / 2:
                ligne[1].append(boite)
                break
        else:
            pente = (y2 - y1) / (x2 - x1) if x2 != x1 else 0
            lignes.append([(pente, milieu_x, milieu_y), [boite]])
    lignes.sort(key=lambda ligne: ligne[0][2] - ligne[0][0] * ligne[0][1])  # y ramené à x = 0
    return [" ".join(b[1] for b in groupe) for _, groupe in lignes]


def _decouper(mot: str) -> str:
    """Coupe un mot collé en mots du vocabulaire (le moins de morceaux possible), sinon le garde."""
    if mot in _VOCABULAIRE:
        return mot
    meilleur: list[list[str] | None] = [[]] + [None] * len(mot)
    for fin in range(1, len(mot) + 1):
        for debut in range(max(0, fin - 15), fin):
            morceaux, actuel = meilleur[debut], meilleur[fin]
            if (
                morceaux is not None
                and mot[debut:fin] in _VOCABULAIRE
                and (actuel is None or len(morceaux) + 1 < len(actuel))
            ):
                meilleur[fin] = [*morceaux, mot[debut:fin]]
    return " ".join(meilleur[-1]) if meilleur[-1] else mot


def nettoyer(libelle: str) -> str:
    """« LT1/2ECRUHT1L » → « lait demi-écrémé 1 l » : texte utilisable pour la recherche."""
    texte = re.sub(r"(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])", " ", libelle).lower()
    texte = re.sub(r"[a-z]{7,}", lambda m: _decouper(m[0]), texte)
    texte = re.sub(r"(?<=\d) (?=/)|(?<=/) (?=\d)", "", texte)  # « 1 / 2 » → « 1/2 »
    for motif, remplacement in _ABREVIATIONS:
        texte = re.sub(motif, remplacement, texte)
    return " ".join(re.sub(r"[^\w/%.,'-]", " ", texte).split())[:120]


def analyser(lignes: list[str]) -> list[tuple[str, int]]:
    """Lignes du ticket → [(recherche, quantité)]. Une ligne « 2 x 1,20 » donne la quantité de
    l'article juste au-dessus."""
    articles: list[list] = []
    for ligne in lignes:
        if re.search(r"\btotal\b", ligne, re.I):
            break
        if (quantite := _QUANTITE.match(ligne.strip())) and articles:
            articles[-1][1] = min(int(quantite[1]), 99)
            continue
        prix = _PRIX_FIN.match(ligne.strip())
        if not prix or _MOTS_IGNORES.search(prix[1]) or len(re.findall(r"[a-zA-Z]", prix[1])) < 3:
            continue
        articles.append([nettoyer(prix[1]), 1])
    return [(recherche, quantite) for recherche, quantite in articles if recherche]
