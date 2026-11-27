export function extractProductPage(adapter, limite = Infinity) {
  const compact = (value) => (typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "");
  const live = (element) => Boolean(element?.getClientRects().length)
    && getComputedStyle(element).visibility === "visible";
  const store = [...document.querySelectorAll(
    '#headerStoreName, [data-store-name], [data-testid*="store-name"], [data-testid*="drive-name"]'
  )].find(live);
  const storeName = compact(store?.innerText).slice(0, 120);

  const read = (node, selector) => compact(node.querySelector(selector)?.innerText);
  const currentPage = location.origin + location.pathname;
  const visibleStore = (pattern) => [...document.querySelectorAll("header")]
    .filter(live).flatMap((header) => header.innerText.split("\n")).map(compact).find((line) => pattern.test(line)) || "";
  const packAndUnit = (text) => {
    const [format, unitPrice] = text.split("•").map(compact);
    const perUnit = unitPrice?.match(/(\d+[,.]\d+)\s*€\s*\/\s*([\p{L}.]+)/u);
    return {format, prix_par_unite_eur: perUnit?.[1].replace(",", ".") || "", unite: perUnit?.[2] || ""};
  };
  const addItem = (index, row) => {
    if (!row.produit || !/^\d+(?:[.,]\d{1,2})?$/.test(row.prix_eur)) return;
    const url = new URL(row.url || currentPage, currentPage);
    if (url.origin !== location.origin) return;
    index.set(row.id_produit_source || row.ean || [url.pathname, row.produit, row.format].join("|"), {
      ean: "", marque: "", format: "", promos: "", id_produit_source: "", prix_par_unite_eur: "", unite: "",
      ...row, prix_eur: row.prix_eur.replace(",", "."), url: url.origin + url.pathname,
    });
  };
  const index = new Map();
  let label = "";
  if (adapter === "u") {
    label = visibleStore(/^super u bruz$/i);
    for (const card of [...document.querySelectorAll('#search-result-items li[data-tc-product-tile]')].slice(0, limite)) {
      const value = card.querySelector("[data-item-price]");
      const link = card.querySelector('a[href*="/p/"]');
      if (!live(value) || !link) continue;
      let data;
      try { data = JSON.parse(card.getAttribute("data-tc-product-tile")); } catch { continue; }
      const promotion = data.promotion?.name;
      addItem(index, {
        produit: compact(data.name), ean: String(data.EAN || ""), marque: compact(data.brand),
        prix_eur: value.getAttribute("data-item-price") || "", url: link.getAttribute("href"),
        promos: promotion === "unknown" ? "" : compact(promotion), id_produit_source: String(data.id || ""),
      });
    }
  }
  if (adapter === "carrefour") {
    label = visibleStore(/chartres-de-bretagne|rennes centre alma/i);
    for (const card of document.querySelectorAll("article.product-list-card-plp-grid-new")) {
      const link = card.querySelector('[data-testid="product-card-primary-link"]');
      const value = card.querySelector(".product-price__amount--main");
      if (!live(value) || !link) continue;
      const lines = link.innerText.split(/\n+/).map(compact).filter(Boolean);
      const promo = [...card.querySelectorAll(".sticker-promo__text")].filter(live).map((node) => compact(node.innerText));
      const ean = card.getAttribute("data-testid") || "";
      addItem(index, {
        produit: lines.at(-1), marque: lines.length > 1 ? lines[0] : "", ean,
        format: read(card, ".product-list-card-plp-grid-new__meta--shimzone"),
        prix_eur: value.innerText.replace(/[\s€]/g, ""), promos: [...new Set(promo)].join(" | "), url: link.getAttribute("href"),
      });
    }
  }
  if (adapter === "leclerc") {
    label = visibleStore(/^bruz\s*-\s*ker lann$/i);
    for (const card of document.querySelectorAll("li.liWCRS310_Product")) {
      const value = card.querySelector(".pWCRS310_PrixUnitairePartieEntiere");
      if (!live(value)) continue;
      const fraction = read(card, ".pWCRS310_PrixUnitairePartieDecimale");
      if (!/^,\d{2}$/.test(fraction)) continue;
      const desc = card.querySelector(".pWCRS310_Desc")?.innerText.split(/\n+/).map(compact).filter(Boolean) || [];
      const image = card.querySelector(".aWCRS310_Product img");
      const id = image?.getAttribute("src")?.match(/[?&]id=(\d+)/)?.[1] || "";
      const promo = card.querySelector('img[alt^="Avantage"], img[alt^="Remise"]')?.getAttribute("alt");
      const link = card.querySelector(".pWCRS310_Desc a[href]")?.getAttribute("href");
      const ean = card.getAttribute("data-ean") || card.querySelector('[itemprop^="gtin"]')?.getAttribute("content") || "";
      addItem(index, {
        produit: desc[0], format: desc.slice(1).join(" "), prix_eur: compact(value.innerText) + fraction,
        id_produit_source: id, ean, promos: compact(promo), url: link?.startsWith("javascript:") ? currentPage : link,
      });
    }
  }
  if (adapter === "intermarche") {
    label = storeName;
    for (const card of [...document.querySelectorAll('[data-navigate-product-item] [data-testid="product-layout"]')].slice(0, limite)) {
      const link = card.querySelector('a[href*="/produit/"]');
      const heading = link?.querySelector(".stime-product--details__title");
      const value = card.querySelector(".stime-product--footer__prices .product--price");
      if (!live(heading) || !live(value)) continue;
      const href = link.getAttribute("href");
      const match = compact(value.innerText).match(/^(\d+[,.]\d{2})\s*€$/);
      if (!match) continue;
      const sticker = card.querySelector('[data-slot="sticker"][aria-label]');
      addItem(index, {
        produit: compact(heading.innerText), prix_eur: match[1], ean: href.match(/\/(\d{13})\/?$/)?.[1] || "",
        marque: read(link, ".stime-product--details__summary p"),
        ...packAndUnit(read(link, ".stime-product--details__packaging")),
        promos: live(sticker) ? compact(sticker.getAttribute("aria-label")) : "", url: href,
      });
    }
  }
  return {items: [...index.values()], store: label, rayon: compact(document.querySelector("main h1")?.innerText) || document.title};
}
