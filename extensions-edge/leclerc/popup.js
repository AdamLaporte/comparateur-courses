import { csv, price, validEan } from "./csv.js";
import { drive } from "./drive.js";
import { appelerApi, normaliserOrigine, origineLocale } from "./connexion.js";
import { lirePage } from "./navigation.js";

const byId = (id) => document.getElementById(id);
const form = byId("form");
const fields = form.elements;
const formMagasin = byId("form-magasin");
const ajoutStatut = byId("ajout-statut");
let magasinDetecte = null;
let rows = [];
let listing = [];
let busy = false;
let pointLu = null;
let rayon = "";

function status(message, error = false) {
  byId("status").textContent = message;
  byId("status").classList.toggle("error", error);
}
function update() {
  byId("count").textContent = rows.length + " relevé" + (rows.length > 1 ? "s" : "");
  byId("export").disabled = busy || !rows.length;
  byId("read").disabled = busy;
  byId("save-list").disabled = busy || !pointLu;
  byId("single").disabled = busy || !pointLu;
}
function matchesSite(url) {
  try {
    const { hostname, protocol } = new URL(url);
    return protocol === "https:" && drive.domains.some((domain) => hostname === domain || hostname.endsWith("." + domain));
  } catch { return false; }
}
async function pointsRepertories() {
  const { jeton, adresseServeur } = await chrome.storage.local.get(["jeton", "adresseServeur"]);
  if (jeton) {
    try {
      const reponse = await appelerApi(adresseServeur, `/enseignes/${drive.enseigneId}/points-retrait`, jeton);
      if (reponse.ok) {
        const points = await reponse.json();
        await chrome.storage.local.set({ catalogueDrives: { origine: normaliserOrigine(adresseServeur), points } });
        return points;
      }
    } catch {
      // Réutiliser le catalogue de cette configuration pour le relevé manuel hors connexion.
    }
  }
  const { catalogueDrives } = await chrome.storage.local.get("catalogueDrives");
  return catalogueDrives?.origine === normaliserOrigine(adresseServeur) ? catalogueDrives.points : [];
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
  const produit = row.id_produit_source || row.ean || row.url + "|" + row.produit + "|" + row.format;
  return row.service_drive + "|" + produit;
}
async function save(items) {
  if (busy || !pointLu) return;
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
        enseigne: drive.enseigne, drive: pointLu.nom, adresse: pointLu.adresse,
        service_drive: pointLu.id, rayon, releve_le: date, source: "releve_drive",
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
  pointLu = null;
  byId("drive-lu").hidden = true;
  showListing([]);
  busy = true;
  update();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!matchesSite(tab?.url)) return status("Ouvre le site marchand d’un point de retrait de l’enseigne.", true);
    const points = await pointsRepertories();
    const resultat = await lireMagasinActif(tab);
    if (resultat.erreur) return status("Le site marchand a bloqué la lecture ou demande une vérification.", true);
    const point = points.find((candidat) => candidat.reference === resultat.reference);
    if (!point) {
      byId("ajout-magasin").open = true;
      return status("Point de retrait non reconnu. Ajoute le magasin actif ou vérifie la connexion au comparateur.", true);
    }
    if (!resultat.items.length) return status("Aucune carte avec prix. Ouvre un rayon ou des résultats de recherche.", true);
    pointLu = point;
    byId("drive-name").textContent = point.nom;
    byId("drive-address").textContent = point.adresse;
    byId("drive-lu").hidden = false;
    rayon = resultat.rayon;
    showListing(resultat.items);
    status(resultat.items.length + " produits détectés.");
  } catch {
    status("Lecture impossible. Réessaie depuis un rayon du drive.", true);
  } finally {
    busy = false;
    update();
  }
});
async function lireMagasinActif(tab) {
  if (!tab) [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!matchesSite(tab?.url)) return null;
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id }, func: lirePage,
  });
  return result;
}
byId("detecter-magasin").addEventListener("click", async (event) => {
  const bouton = event.currentTarget;
  bouton.disabled = true;
  formMagasin.hidden = true;
  formMagasin.reset();
  magasinDetecte = null;
  ajoutStatut.textContent = "Détection du magasin actif…";
  try {
    const resultat = await lireMagasinActif();
    if (!resultat?.reference || !resultat.items.length) {
      ajoutStatut.textContent = "Retrait introuvable. Ouvre un rayon ou une recherche avec des prix après avoir choisi le drive.";
      return;
    }
    magasinDetecte = resultat;
    formMagasin.elements.libelle.value = resultat.libelle;
    formMagasin.elements.codePostal.value = resultat.codePostal;
    ajoutStatut.textContent = `Drive détecté (${resultat.reference}). Confirme son nom et son adresse.`;
    formMagasin.hidden = false;
  } catch {
    ajoutStatut.textContent = "Lecture impossible. Réessaie depuis le site marchand.";
  } finally {
    bouton.disabled = false;
  }
});
formMagasin.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!magasinDetecte) return;
  const bouton = event.submitter;
  bouton.disabled = true;
  byId("detecter-magasin").disabled = true;
  ajoutStatut.textContent = "Enregistrement du retrait…";
  try {
    const { jeton, adresseServeur } = await chrome.storage.local.get(["jeton", "adresseServeur"]);
    if (!jeton) {
      ajoutStatut.textContent = "Configure d’abord la connexion au comparateur.";
      return;
    }
    const actuel = await lireMagasinActif();
    if (actuel?.reference !== magasinDetecte.reference || !actuel.items.length) {
      ajoutStatut.textContent = "Le retrait actif a changé. Relance la détection.";
      formMagasin.hidden = true;
      magasinDetecte = null;
      return;
    }
    const champs = formMagasin.elements;
    const reponse = await appelerApi(
      adresseServeur, `/enseignes/${drive.enseigneId}/inscrire-point-retrait`, jeton,
      {
        reference: actuel.reference,
        libelle: champs.libelle.value.trim(),
        accueil: actuel.accueil,
        adresse: champs.adresse.value.trim(),
        code_postal: champs.codePostal.value.trim(),
      },
    );
    if (!reponse.ok) {
      const erreur = await reponse.json().catch(() => ({}));
      ajoutStatut.textContent = typeof erreur.detail === "string"
        ? erreur.detail : "Vérifie le nom et l’adresse du magasin, puis réessaie.";
      return;
    }
    const point = await reponse.json();
    await pointsRepertories();
    ajoutStatut.textContent = `${point.nom} est disponible en mode Données réelles.`;
    formMagasin.hidden = true;
    magasinDetecte = null;
  } catch {
    ajoutStatut.textContent = "Impossible de joindre le comparateur.";
  } finally {
    bouton.disabled = false;
    byId("detecter-magasin").disabled = false;
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
  link.download = drive.enseigneId + "_" + new Date().toISOString().slice(0, 10) + ".csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1500);
});
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
