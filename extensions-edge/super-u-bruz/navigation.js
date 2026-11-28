// Cette fonction s'exécute dans l'onglet marchand. Seuls les signaux nécessaires en sortent.
export function lirePage(adaptateur, requete, soumettre, points) {
  const compacte = (texte) => (texte || "").replace(/\s+/g, " ").trim();
  const normalise = (texte) => compacte(texte).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const visible = (element) => Boolean(element?.getClientRects().length)
    && getComputedStyle(element).visibility === "visible";
  const titre = compacte(document.title);
  const principal = document.querySelector("main");
  const entete = [...document.querySelectorAll("header")].filter(visible);
  const textePrincipal = principal?.innerText || "";
  const navigation = performance.getEntriesByType("navigation")[0];
  const statut = navigation?.responseStatus || 0;
  if ([403, 404, 429].includes(statut)) return { erreur: String(statut) };
  if (/^(attention required!|just a moment|access denied|captcha|verify you are human)/i.test(titre)
      || document.querySelector('iframe[src*="captcha-delivery.com"]')) {
    return { erreur: "defi" };
  }
  if (statut >= 400) return { erreur: "page_inattendue" };

  const intermarche = adaptateur === "intermarche";
  const boutonMagasin = document.querySelector("#headerStoreName");
  const libelle = visible(boutonMagasin) ? compacte(boutonMagasin.innerText) : "";
  const livraison = /\blivraison\b/i.test(libelle) || entete.some((element) =>
    [...element.querySelectorAll('[aria-selected="true"], [aria-checked="true"], input:checked')]
      .some((mode) => visible(mode) && /livraison/i.test(mode.innerText || mode.value || "")));
  const correspondance = (point, texte) => point.libelles.some((nom) => normalise(nom) === normalise(texte));
  const refs = new Set();
  const lignes = entete.flatMap((element) => element.innerText.split("\n"));
  let candidats = [];
  if (intermarche && !livraison) {
    // Ce champ du document hydraté alimente le panier du magasin actif.
    for (const script of document.scripts) {
      if (!script.textContent.trimStart().startsWith("self.__next_f.push([1,")) continue;
      for (const ref of script.textContent.matchAll(/\\?"pdvRefFicheMagasin\\?"\s*:\s*\\?"(\d{5}(?:_\d+)?)\\?"/g)) {
        refs.add(ref[1]);
      }
    }
    if (refs.size === 1) {
      candidats = points.filter((point) => refs.has(point.reference ?? point.id) && correspondance(point, libelle));
    }
  } else if (!intermarche && !livraison) {
    // Le numéro du magasin actif est présent même si Courses U n'a pas dessiné l'en-tête.
    for (const script of document.scripts) {
      for (const choix of script.textContent.matchAll(/COOPU\.storeID\s*=\s*["']?(\d+)/g)) {
        refs.add(choix[1]);
      }
    }
    if (refs.size === 1) {
      candidats = points.filter((point) => refs.has(point.reference ?? point.id));
    } else if (refs.size === 0) {
      candidats = points.filter((point) => lignes.some((ligne) => correspondance(point, ligne)));
    }
  }
  const retrait = candidats.length === 1 ? candidats[0].id : "";

  if (soumettre) {
    if (!retrait || retrait !== points[0].id) return { erreur: "mauvais_drive" };
    const champs = [...document.querySelectorAll('input[type="search"], [role="search"] input, input[role="searchbox"]')]
      .filter((champ) => visible(champ) && !champ.disabled && !champ.readOnly);
    if (champs.length !== 1) return { erreur: "page_inattendue" };
    const champ = champs[0];
    const form = champ.form;
    if (!form || form.method !== "get" || !champ.name || !["_self", ""].includes(form.target)) {
      return { erreur: "page_inattendue" };
    }
    if (new URL(form.action, location.href).origin !== location.origin) {
      return { erreur: "page_inattendue" };
    }
    champ.focus();
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(champ, requete);
    champ.dispatchEvent(new Event("input", { bubbles: true }));
    form.requestSubmit();
    return { retrait };
  }

  const url = new URL(location.href);
  const cle = normalise(requete);
  const chemin = cle ? decodeURIComponent(url.pathname).replace(/\/$/, "") : "";
  const recherche = Boolean(cle) && (intermarche
    ? normalise(chemin) === "/recherche/" + cle
    : ([...url.searchParams.values()].some((valeur) => normalise(valeur) === cle)
      || normalise(chemin.split("/").at(-1)) === cle));
  const selecteur = intermarche
    ? '[data-navigate-product-item] [data-testid="product-layout"]'
    : "#search-result-items li[data-tc-product-tile]";
  const cartes = Math.min(document.querySelectorAll(selecteur).length, 60);
  // Un texte vide dans la grille peut aussi signaler un chargement ou une erreur.
  const vide = recherche && cartes === 0 && textePrincipal.split("\n").some((ligne) =>
    /^(?:0 resultats?|aucun (?:resultat|produit)(?: trouve)?(?: pour cette recherche)?)[.!]?$/i
      .test(normalise(ligne)));
  return {
    retrait,
    recherche,
    cartes,
    vide,
    charge: document.readyState === "complete" && Boolean(principal),
    document: performance.timeOrigin,
  };
}
