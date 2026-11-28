// Cette fonction est injectée dans l'onglet. Elle ne fait aucun appel réseau.
export function lirePage(requete = "") {
  const compacte = (texte) => typeof texte === "string" ? texte.replace(/\s+/g, " ").trim() : "";
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
  const recherche = Boolean(requete) && url.pathname.replace(/\/$/, "") === "/s"
    && normalise(url.searchParams.get("q")) === normalise(requete);
  const principal = document.querySelector("main");
  const libelle = [...document.querySelectorAll(
    'header [data-store-name], header [data-testid*="store-name"], header [data-testid*="drive-name"]',
  )].filter(visible).map((element) => compacte(element.innerText)).find(Boolean) || "";
  const depart = {
    reference: "",
    accueil: "",
    libelle,
    codePostal: "",
    items: [],
    cartes: 0,
    recherche,
    charge: document.readyState === "complete" && Boolean(principal),
    document: performance.timeOrigin,
    rayon: compacte(principal?.querySelector("h1")?.innerText),
  };
  const estLivraison = [...document.querySelectorAll('header [aria-selected="true"], header [aria-checked="true"]')]
    .some((element) => visible(element) && /\blivraison\b/.test(normalise(element.innerText)));
  if (estLivraison || /\blivraison\b/.test(normalise(libelle))) return depart;

  let table, lire, donnees;
  for (const script of document.scripts) {
    const chaine = script.textContent.match(/"routeData"\s*:\s*("(?:[^"\\]|\\.)*")/);
    if (!chaine) continue;
    try {
      table = JSON.parse(JSON.parse(chaine[1]));
    } catch {
      continue;
    }
    if (!Array.isArray(table)) continue;
    lire = (valeur) => Number.isInteger(valeur) ? table[valeur] : valeur;
    donnees = lire(table[0]?.data);
    if (Array.isArray(donnees)) break;
  }
  if (!Array.isArray(donnees)) return depart;

  const liens = new Map();
  for (const carte of document.querySelectorAll("article.product-list-card-plp-grid-new")) {
    const ancre = carte.querySelector('[data-testid="product-card-primary-link"][href]');
    if (!ancre) continue;
    const lien = new URL(ancre.href);
    if (lien.origin !== url.origin || !lien.pathname.startsWith("/p/")) continue;
    const ean = /^\d{8,14}$/.test(carte.dataset.testid || "") ? carte.dataset.testid
      : lien.pathname.match(/(?:-|\/)(\d{8,14})\/?$/)?.[1];
    if (!ean) continue;
    liens.set(ean, {
      url: lien.origin + lien.pathname,
      format: compacte(carte.querySelector(".product-list-card-plp-grid-new__meta--shimzone")?.innerText),
    });
  }
  const refs = new Set();
  const items = new Map();
  const montant = (prix, precision) => {
    if (typeof prix !== "number" && typeof prix !== "string") return "";
    const decimal = String(prix).replace(",", ".");
    return new RegExp("^\\d+(?:\\.\\d{1," + precision + "})?$").test(decimal) ? decimal : "";
  };
  for (const entree of donnees) {
    const attributs = lire(lire(entree)?.attributes);
    const ean = String(lire(attributs?.ean) ?? "");
    if (!/^\d{8,14}$/.test(ean)) continue;
    const offres = lire(lire(attributs.offers)?.[ean]);
    if (!offres || typeof offres !== "object") continue;
    for (const [cle, donnee] of Object.entries(offres)) {
      // Le canal Drive de Carrefour lie chaque tarif à une référence de retrait.
      const reference = cle.match(/^0039-150-(\d{1,12})$/)?.[1];
      if (!reference) continue;
      refs.add(reference);
      if (items.size >= 60) continue;
      const offre = lire(lire(donnee)?.attributes);
      const prix = lire(offre?.price);
      const prixEuros = montant(lire(prix?.price), 2);
      const produit = compacte(lire(attributs.title));
      if (!prixEuros || !produit || lire(offre?.available) === false) continue;
      const promos = lire(offre?.promotions);
      const conditions = Array.isArray(promos)
        ? [...new Set(promos.map((promo) => compacte(lire(lire(promo)?.label))).filter(Boolean))] : [];
      items.set(ean, {
        produit,
        ean,
        marque: compacte(lire(attributs.brand)),
        format: liens.get(ean)?.format || compacte(lire(attributs.packaging)),
        prix_eur: prixEuros,
        prix_par_unite_eur: montant(lire(prix?.perUnit), 4),
        unite: compacte(lire(prix?.unitOfMeasure)),
        promos: conditions.join(" | ").slice(0, 500),
        url: liens.get(ean)?.url || url.origin + url.pathname,
      });
    }
  }
  if (refs.size !== 1) return depart;
  const [reference] = refs;
  return {
    ...depart,
    reference,
    accueil: url.origin + "/set-store/" + reference,
    items: [...items.values()],
    cartes: donnees.length,
  };
}
