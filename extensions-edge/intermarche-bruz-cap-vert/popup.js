import { extractProductPage } from "./extract.js";
import { csv, price, validEan } from "./csv.js";
import { drive } from "./drive.js";
import { appelerApi, normaliserOrigine, origineLocale } from "./connexion.js";

const byId = (id) => document.getElementById(id);
const form = byId("form");
const fields = form.elements;
let rows = [];
let listing = [];
let busy = false;
let verified = false;
let rayon = "";

function status(message, error = false) {
  byId("status").textContent = message;
  byId("status").classList.toggle("error", error);
}
function update() {
  byId("count").textContent = rows.length + " relevé" + (rows.length > 1 ? "s" : "");
  byId("export").disabled = busy || !rows.length;
  byId("read").disabled = busy;
  byId("save-list").disabled = busy || !verified;
  byId("single").disabled = busy || !verified;
}
function matchesSite(url) {
  try {
    const { hostname, protocol } = new URL(url);
    return protocol === "https:" && drive.domains.some((domain) => hostname === domain || hostname.endsWith("." + domain));
  } catch { return false; }
}
function fillItem(item) {
  for (const key of ["produit", "prix_eur", "ean", "marque", "format", "promos", "url"]) {
    fields[key].value = item[key] || "";
  }
  fields.confirme.checked = false;
}
function showListing(items) {
  listing = items;
  byId("listing").hidden = !items.length;
  byId("save-list").hidden = !items.length;
  byId("single").hidden = !items.length;
  byId("items").replaceChildren(...items.map((item, index) =>
    new Option(item.produit + " — " + item.prix_eur.replace(".", ",") + " €", index)));
  byId("save-list").textContent = "Enregistrer les " + items.length + " produits affichés";
  fillItem(items[0] || {});
}
function rowKey(row) {
  return row.id_produit_source || row.ean || row.url + "|" + row.produit + "|" + row.format;
}
async function save(items) {
  if (busy || !verified) return;
  if (!fields.confirme.checked) return status("Confirme le drive et les prix avant d’enregistrer.", true);
  busy = true;
  update();
  try {
    const date = new Date().toISOString();
    const next = new Map(rows.map((row) => [rowKey(row), row]));
    for (const item of items) {
      const amount = price(item.prix_eur);
      if (amount === null || !item.produit.trim() || !matchesSite(item.url)) {
        status("Vérifie le nom du produit, son prix et le lien marchand.", true);
        return;
      }
      const row = {
        ...item, prix_eur: amount, ean: validEan(item.ean) ? item.ean : "",
        enseigne: drive.enseigne, drive: drive.name, adresse: drive.address,
        service_drive: drive.id, rayon, releve_le: date, source: "releve_drive",
      };
      next.set(rowKey(row), row);
    }
    const result = [...next.values()];
    await chrome.storage.local.set({ rows: result });
    const added = result.length - rows.length;
    rows = result;
    fields.confirme.checked = false;
    status(items.length + " relevé(s) enregistré(s), dont " + added + " nouveau(x).");
  } catch {
    status("Enregistrement impossible. Réessaie ou exporte les relevés déjà sauvegardés.", true);
  } finally {
    busy = false;
    update();
  }
}
byId("read").addEventListener("click", async () => {
  if (busy) return;
  verified = false;
  showListing([]);
  busy = true;
  update();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!matchesSite(tab?.url)) return status("Ouvre le site marchand du drive indiqué.", true);
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, func: extractProductPage, args: [drive.adapter],
    });
    if (!result.store || !new RegExp(drive.store, "i").test(result.store)) {
      return status("Drive attendu : " + drive.name + ". Drive affiché : " + (result.store || "non détecté") + ".", true);
    }
    if (!result.items.length) return status("Aucune carte avec prix. Ouvre un rayon ou des résultats de recherche.", true);
    verified = true;
    rayon = result.rayon;
    showListing(result.items);
    status(result.items.length + " produits détectés. Drive affiché : " + result.store + ".");
  } catch {
    status("Lecture impossible. Réessaie depuis un rayon du drive.", true);
  } finally {
    busy = false;
    update();
  }
});
byId("items").addEventListener("change", (event) => fillItem(listing[Number(event.target.value)]));
form.addEventListener("input", (event) => {
  if (event.target !== fields.confirme) fields.confirme.checked = false;
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const item = { ...listing[Number(byId("items").value)] };
  for (const key of ["produit", "prix_eur", "ean", "marque", "format", "promos", "url"]) item[key] = fields[key].value.trim();
  await save([item]);
});
byId("save-list").addEventListener("click", () => save(listing));
byId("export").addEventListener("click", () => {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv(rows)], { type: "text/csv;charset=utf-8" }));
  link.download = drive.slug + "_" + new Date().toISOString().slice(0, 10) + ".csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1500);
});
byId("drive-name").textContent = drive.name;
byId("drive-address").textContent = drive.address;
const collecteStatut = byId("collecte-statut");
chrome.storage.local.get(["jeton", "suspendu", "adresseServeur"]).then(({ jeton, suspendu, adresseServeur }) => {
  byId("adresse-serveur").value = adresseServeur || origineLocale;
  byId("jeton").value = jeton || "";
  collecteStatut.textContent = jeton && !suspendu ? "Collecte automatique activée." : "Collecte inactive.";
});
byId("activer").addEventListener("click", async () => {
  const jeton = byId("jeton").value.trim();
  if (!jeton) {
    collecteStatut.textContent = "Saisis le jeton de collecte fourni pour ce comparateur.";
    return;
  }
  let origine;
  try {
    origine = normaliserOrigine(byId("adresse-serveur").value);
  } catch {
    collecteStatut.textContent = "Saisis l’adresse locale ou l’adresse HTTPS donnée par Tailscale.";
    return;
  }
  try {
    if (origine !== origineLocale && !await chrome.permissions.request({ origins: [origine + "/*"] })) {
      collecteStatut.textContent = "Autorise l’accès à l’adresse du comparateur pour activer la collecte.";
      return;
    }
    const reponse = await appelerApi(
      origine, `/enseignes/${drive.enseigneId}/connexion`, jeton,
    ).catch(() => null);
    if (!reponse?.ok) {
      collecteStatut.textContent = reponse?.status === 401
        ? "Jeton refusé par le comparateur."
        : "Comparateur inaccessible à cette adresse.";
      return;
    }
    await chrome.storage.local.set({ adresseServeur: origine, jeton, suspendu: false });
    collecteStatut.textContent = "Serveur connecté. L’onglet marchand s’ouvrira au premier relevé.";
    void chrome.runtime.sendMessage("releve-drive").catch(() => {});
  } catch {
    collecteStatut.textContent = "Impossible d’enregistrer la configuration.";
  }
});
byId("desactiver").addEventListener("click", async () => {
  await chrome.storage.local.set({ suspendu: true });
  collecteStatut.textContent = "Collecte inactive.";
});
chrome.storage.local.get({ rows: [] }).then((data) => {
  rows = data.rows;
  update();
}).catch(() => status("Impossible de charger les relevés.", true));
