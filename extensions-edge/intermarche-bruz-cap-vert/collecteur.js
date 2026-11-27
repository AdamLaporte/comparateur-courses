import { drive } from "./drive.js";
import { extractProductPage } from "./extract.js";
import { lirePage } from "./navigation.js";

const api = "http://127.0.0.1:8000/api/drives";
const reveil = "releve-drive";
const erreursNavigation = new Map();
let occupe = false;
let tabEnCours = null;

function siteDuDrive(adresse) {
  try {
    const { protocol, hostname } = new URL(adresse);
    return protocol === "https:" && drive.domains.some((hote) =>
      hostname === hote || hostname.endsWith("." + hote));
  } catch {
    return false;
  }
}

async function appeler(route, jeton, corps) {
  return fetch(api + route, {
    method: "POST",
    credentials: "omit",
    redirect: "error",
    signal: AbortSignal.timeout(5000),
    headers: { "X-Drives-Jeton": jeton, "Content-Type": "application/json" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
}

async function injecter(target, func, ...args) {
  const [reponse] = await chrome.scripting.executeScript({ target, func, args });
  return reponse;
}

async function ouvrirOnglet(identifiant) {
  const existant = identifiant && await chrome.tabs.get(identifiant).catch(() => null);
  if (existant && siteDuDrive(existant.url)) return existant.id;
  const onglet = await chrome.tabs.create({ active: false });
  await chrome.storage.session.set({ ongletCollecte: onglet.id });
  return onglet.id;
}

async function verifierRetrait(cible, limite) {
  let boutonUtilise = false;
  while (Date.now() < limite) {
    if (erreursNavigation.has(cible.tabId)) return { erreur: erreursNavigation.get(cible.tabId) };
    const onglet = await chrome.tabs.get(cible.tabId);
    if (onglet.status === "complete" && siteDuDrive(onglet.url)) {
      const page = await injecter(cible, lirePage, drive.adapter);
      if (page.result.erreur || page.result.retrait === drive.id) return page.result;
      if (!boutonUtilise && drive.adapter === "intermarche" && onglet.url === drive.accueil) {
        boutonUtilise = true;
        await injecter(cible, () => {
          const boutons = [...document.querySelectorAll("button, a[href]")].filter((bouton) =>
            bouton.getClientRects().length && bouton.innerText.trim() === "Faire mes courses");
          if (boutons.length === 1) boutons[0].click();
        });
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  return { erreur: "mauvais_drive" };
}

async function relever(tabId, requete) {
  const cible = { tabId };
  tabEnCours = tabId;
  erreursNavigation.delete(tabId);
  try {
    const initial = await chrome.tabs.get(tabId);
    if (!siteDuDrive(initial.url)) await chrome.tabs.update(tabId, { url: drive.accueil });
    const depart = await verifierRetrait(cible, Date.now() + 18_000);
    if (depart.erreur) return { erreur: depart.erreur };
    const tab = await chrome.tabs.get(tabId);
    if (!siteDuDrive(tab.url)) return { erreur: "page_inattendue" };

    if (drive.adapter === "intermarche") {
      // Route utilisée par le bouton de recherche dans les scripts de la page de référence.
      const destination = new URL("/recherche/" + encodeURIComponent(requete), tab.url);
      if (tab.url === destination.href) await chrome.tabs.reload(tabId);
      else await chrome.tabs.update(tabId, { url: destination.href });
    } else {
      const { result } = await injecter(cible, lirePage, drive.adapter, requete, true);
      if (result.erreur) return { erreur: result.erreur };
    }

    const limite = Date.now() + 30_000;
    let precedent = "";
    while (Date.now() < limite) {
      await new Promise((resolve) => setTimeout(resolve, 700));
      if (erreursNavigation.has(tabId)) return { erreur: erreursNavigation.get(tabId) };
      const onglet = await chrome.tabs.get(tabId);
      if (!siteDuDrive(onglet.url)) return { erreur: "page_inattendue" };
      if (onglet.status !== "complete") continue;
      let page;
      try {
        page = await injecter(cible, lirePage, drive.adapter, requete);
      } catch {
        continue;
      }
      const etat = page.result;
      if (etat.erreur) return { erreur: etat.erreur };
      if (etat.document === depart.document) continue;
      if (!etat.recherche || !etat.charge) continue;
      if (etat.retrait !== drive.id) return { erreur: "mauvais_drive" };
      // Attendre deux lectures stables dans le document de résultats.
      const signature = [page.documentId, etat.cartes, etat.vide].join("|");
      if (signature !== precedent) {
        precedent = signature;
        continue;
      }
      if (etat.vide) return { etat: "vide", service_observe: etat.retrait };
      if (etat.cartes === 0) continue;
      const documentResultats = { tabId, documentIds: [page.documentId] };
      const { result } = await injecter(documentResultats, extractProductPage, drive.adapter, 60);
      const { result: verification } = await injecter(
        documentResultats, lirePage, drive.adapter, requete,
      );
      if (verification.erreur) return { erreur: verification.erreur };
      if (verification.retrait !== drive.id) return { erreur: "mauvais_drive" };
      if (!verification.recherche) return { erreur: "page_inattendue" };
      if (result.items.length) {
        return { etat: "succes", service_observe: verification.retrait, produits: result.items };
      }
    }
    return { erreur: "delai" };
  } catch {
    return { erreur: erreursNavigation.get(tabId) || "page_inattendue" };
  } finally {
    erreursNavigation.delete(tabId);
    tabEnCours = null;
  }
}

async function livrer(jeton, message) {
  const reponse = await appeler(`/taches/${message.id}/depot`, jeton, message.depot);
  if (reponse.ok || reponse.status === 409) {
    await chrome.storage.session.remove("depot");
    return true;
  }
  if (reponse.status === 422) {
    const { drive_id, bail } = message.depot;
    const erreur = { drive_id, bail, etat: "echec", erreur: "page_inattendue" };
    const rejet = await appeler(`/taches/${message.id}/depot`, jeton, erreur);
    if (rejet.ok || rejet.status === 409) await chrome.storage.session.remove("depot");
  }
  return false;
}

async function collecter() {
  if (occupe) return;
  occupe = true;
  try {
    const { jeton, suspendu } = await chrome.storage.local.get(["jeton", "suspendu"]);
    const { ongletCollecte, depot } = await chrome.storage.session.get(["ongletCollecte", "depot"]);
    if (!jeton) return;
    if (depot && !await livrer(jeton, depot)) return;
    if (suspendu) return;
    const reponse = await appeler(`/${drive.serveurId}/prendre`, jeton);
    if (!reponse.ok) return;
    const tache = await reponse.json();
    if (!tache || tache.drive_id !== drive.serveurId) return;
    let resultat;
    try {
      resultat = await relever(await ouvrirOnglet(ongletCollecte), tache.requete);
    } catch {
      resultat = { erreur: "page_inattendue" };
    }
    const message = {
      id: tache.id,
      depot: {
        drive_id: drive.serveurId,
        bail: tache.bail,
        etat: resultat.erreur ? "echec" : resultat.etat,
        ...resultat,
      },
    };
    await chrome.storage.session.set({ depot: message });
    await livrer(jeton, message);
  } catch {
    // Serveur local fermé ou temporairement inaccessible. Réessayer au prochain réveil.
  } finally {
    occupe = false;
  }
}

const filtre = { urls: drive.domains.map((nom) => `https://*.${nom}/*`), types: ["main_frame", "xmlhttprequest"] };
chrome.webRequest.onCompleted.addListener(({ tabId, statusCode, type }) => {
  if (tabId === tabEnCours && ([403, 429].includes(statusCode) || (type === "main_frame" && statusCode === 404))) {
    erreursNavigation.set(tabId, String(statusCode));
  }
}, filtre);
chrome.webRequest.onErrorOccurred.addListener(({ tabId, error, type }) => {
  if (tabId === tabEnCours && type === "main_frame" && error !== "net::ERR_ABORTED") {
    erreursNavigation.set(tabId, "reseau");
  }
}, filtre);
chrome.tabs.onRemoved.addListener(async (tabId) => {
  erreursNavigation.delete(tabId);
  const { ongletCollecte } = await chrome.storage.session.get("ongletCollecte");
  if (ongletCollecte === tabId) await chrome.storage.session.remove("ongletCollecte");
});
chrome.alarms.onAlarm.addListener(({ name }) => {
  if (name === reveil) void collecter();
});
chrome.runtime.onMessage.addListener((message, expediteur) => {
  if (expediteur.id === chrome.runtime.id && message === reveil) void collecter();
});
chrome.runtime.onStartup.addListener(() => void collecter());
chrome.runtime.onInstalled.addListener(() => void collecter());
chrome.alarms.get(reveil).then((alarme) => {
  if (!alarme) return chrome.alarms.create(reveil, { periodInMinutes: 0.5 });
}).catch(() => {});
