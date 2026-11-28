// Les prix sont lus dans les cartes du catalogue déjà affiché par le navigateur.
export function lirePage(requete = "") {
  const compacte = (texte) => (texte || "").replace(/\s+/g, " ").trim();
  const normalise = (texte) => compacte(texte).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const visible = (element) => Boolean(element?.getClientRects().length)
    && getComputedStyle(element).visibility === "visible";
  const statut = performance.getEntriesByType("navigation")[0]?.responseStatus || 0;
  if ([403, 404, 429].includes(statut)) return { erreur: String(statut) };
  if (/^(attention required!|just a moment|access denied|captcha|verify you are human)/i.test(document.title)
      || document.querySelector('iframe[src*="captcha-delivery.com"], #challenge-form')) {
    return { erreur: "defi" };
  }
  if (statut >= 400) return { erreur: "page_inattendue" };

  const url = new URL(location.href);
  const [, chemin, reference, slug] = url.pathname.match(
    /^(\/magasin-(\d{6})-([^/]+?))(?:\.aspx)?(?:\/|$)/i,
  ) || [];
  const principal = document.querySelector("main, [role='main']");
  const titre = compacte(principal?.querySelector("h1")?.innerText);
  const recherche = Boolean(requete) && /\/recherche\.aspx\/?$/i.test(url.pathname)
    && normalise(url.searchParams.get("TexteRecherche")) === normalise(requete);
  const livraison = [...document.querySelectorAll('header [aria-selected="true"], header [aria-checked="true"]')]
    .some((element) => visible(element) && /\blivraison\b/.test(normalise(element.innerText)));
  const etat = {
    reference: "",
    accueil: "",
    libelle: "",
    codePostal: "",
    recherche,
    cartes: 0,
    items: [],
    charge: document.readyState === "complete",
    document: performance.timeOrigin,
    rayon: titre,
  };
  if (!reference || livraison) return etat;
  const libelleSecours = decodeURIComponent(slug).replace(new RegExp("^" + reference + "-"), "")
    .replace(/-+/g, " ");
  const nomActif = [...document.querySelectorAll(
    'header [data-store-name], header [data-testid*="store-name"], header [data-testid*="drive-name"]',
  )].filter(visible).map((element) => compacte(element.innerText)).find(Boolean);
  if (/\blivraison\b/.test(normalise(nomActif))) return etat;

  const cartes = [...document.querySelectorAll("li.liWCRS310_Product")].slice(0, 60);
  const items = [];
  for (const carte of cartes) {
    const euros = carte.querySelector(".pWCRS310_PrixUnitairePartieEntiere");
    const centimes = compacte(carte.querySelector(".pWCRS310_PrixUnitairePartieDecimale")?.innerText);
    const entier = compacte(euros?.innerText).replace(/\s/g, "");
    if (!visible(euros) || !/^\d+$/.test(entier) || !/^,\d{2}$/.test(centimes)) continue;
    const description = carte.querySelector(".pWCRS310_Desc");
    const [produit, ...format] = (description?.innerText || "").split(/\n+/).map(compacte).filter(Boolean);
    if (!produit) continue;
    const image = carte.querySelector(".aWCRS310_Product img");
    const id = image?.getAttribute("src")?.match(/[?&]id=(\d+)/)?.[1] || "";
    const promo = carte.querySelector('img[alt^="Avantage"], img[alt^="Remise"]')?.getAttribute("alt");
    const ancre = description.querySelector("a[href]");
    const lien = new URL(ancre?.href || url.href);
    const adresseArticle = lien.origin === url.origin && lien.pathname.startsWith(chemin + "/")
      ? lien.origin + lien.pathname : url.origin + url.pathname;
    const ean = carte.dataset.ean || compacte(carte.querySelector('[itemprop^="gtin"]')?.getAttribute("content"));
    const unite = [...carte.querySelectorAll("p, span")]
      .map((element) => compacte(element.innerText).match(/^(\d+[,.]\d{2,4})\s*€\s*\/\s*(kg|l|unité)$/i))
      .find(Boolean);
    items.push({
      produit, ean, format: format.join(" "),
      id_produit_source: id,
      prix_eur: entier + centimes.replace(",", "."),
      prix_par_unite_eur: unite?.[1].replace(",", ".") || "",
      unite: unite?.[2] || "",
      promos: compacte(promo),
      url: adresseArticle,
    });
  }
  const vide = recherche && cartes.length === 0 && (principal?.innerText || "").split("\n").some((ligne) =>
    /^(?:0 resultats?|aucun (?:resultat|produit)(?: trouve)?(?: pour cette recherche)?)[.!]?$/i
      .test(normalise(ligne)));
  return {
    ...etat,
    reference,
    accueil: url.origin + chemin + ".aspx",
    libelle: nomActif || "E.Leclerc Drive " + libelleSecours,
    items,
    cartes: cartes.length,
    vide,
  };
}
