import { drive, urlRecherche } from "./drive.js";
import { lirePage } from "./navigation.js";
import { appelerApi, normaliserOrigine } from "./connexion.js";

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

async function accueilConnu(point) {
  const onglets = await chrome.tabs.query({
    url: `https://*.leclercdrive.fr/magasin-${point.reference}-*`,
  });
  for (const onglet of onglets) {
    if (onglet.status !== "complete" || onglet.pendingUrl || !siteDuDrive(onglet.url)) continue;
    const page = await injecter({ tabId: onglet.id }, lirePage).catch(() => null);
    if (page?.result?.reference === point.reference && siteDuDrive(page.result.accueil)) {
      return page.result.accueil;
    }
  }
  return point.accueil;
}

async function attendreDepart(cible, limite, point, documentPrecedent) {
  let erreur = "delai";
  while (Date.now() < limite) {
    if (erreursNavigation.has(cible.tabId)) return { erreur: erreursNavigation.get(cible.tabId) };
    const onglet = await chrome.tabs.get(cible.tabId);
    if (onglet.status === "complete" && !onglet.pendingUrl && siteDuDrive(onglet.url)) {
      const page = await injecter(cible, lirePage).catch(() => null);
      if (page && page.documentId !== documentPrecedent) {
        const etat = page.result;
        if (etat.erreur || etat.reference === point.reference) return etat;
        erreur = etat.reference ? "mauvais_drive" : "page_inattendue";
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  return { erreur };
}

async function relever(tabId, requete, point, changer) {
  const cible = { tabId };
  tabEnCours = tabId;
  erreursNavigation.delete(tabId);
  try {
    const initial = await chrome.tabs.get(tabId);
    const dejaOuvert = siteDuDrive(initial.url);
    let documentPrecedent;
    if (changer || !dejaOuvert) {
      if (dejaOuvert) documentPrecedent = (await injecter(cible, lirePage).catch(() => null))?.documentId;
      await chrome.tabs.update(tabId, { url: await accueilConnu(point) });
    }
    const depart = await attendreDepart(cible, Date.now() + 18_000, point, documentPrecedent);
    if (depart.erreur) return { erreur: depart.erreur };
    const tab = await chrome.tabs.get(tabId);
    if (!siteDuDrive(tab.url)) return { erreur: "page_inattendue" };

    const destination = urlRecherche(depart.accueil, requete);
    if (tab.url === destination) await chrome.tabs.reload(tabId);
    else await chrome.tabs.update(tabId, { url: destination });

    const limite = Date.now() + 30_000;
    let precedent = "";
    while (Date.now() < limite) {
      await new Promise((resolve) => setTimeout(resolve, 700));
      if (erreursNavigation.has(tabId)) return { erreur: erreursNavigation.get(tabId) };
      const onglet = await chrome.tabs.get(tabId);
      if (onglet.status !== "complete" || onglet.pendingUrl) continue;
      if (!siteDuDrive(onglet.url)) return { erreur: "page_inattendue" };
      let page;
      try {
        page = await injecter(cible, lirePage, requete);
      } catch {
        continue;
      }
      const etat = page.result;
      if (etat.erreur) return { erreur: etat.erreur };
      if (etat.document === depart.document) continue;
      if (!etat.recherche || !etat.charge) continue;
      // L'identité et les prix proviennent de la même lecture du document marchand.
      const signature = JSON.stringify([page.documentId, etat.reference, etat.vide, etat.items]);
      if (signature !== precedent) {
        precedent = signature;
        continue;
      }
      if (!etat.vide && !etat.items.length) continue;
      if (etat.reference !== point.reference) return { erreur: "mauvais_drive" };
      if (etat.vide) return { etat: "vide", service_observe: point.id };
      return { etat: "succes", service_observe: point.id, produits: etat.items };
    }
    return { erreur: "delai" };
  } catch {
    return { erreur: erreursNavigation.get(tabId) || "page_inattendue" };
  } finally {
    erreursNavigation.delete(tabId);
    tabEnCours = null;
  }
}

async function livrer(origine, jeton, message) {
  const route = `/taches/${message.id}/depot`;
  const reponse = await appelerApi(origine, route, jeton, message.depot);
  if (reponse.ok || reponse.status === 409) {
    await chrome.storage.session.remove("depot");
    return true;
  }
  if (reponse.status === 422) {
    const { drive_id, bail } = message.depot;
    const erreur = { drive_id, bail, etat: "echec", erreur: "page_inattendue" };
    const rejet = await appelerApi(origine, route, jeton, erreur);
    if (rejet.ok || rejet.status === 409) await chrome.storage.session.remove("depot");
  }
  return false;
}

async function collecter() {
  if (occupe) return;
  occupe = true;
  try {
    const { jeton, suspendu, adresseServeur } = await chrome.storage.local.get(
      ["jeton", "suspendu", "adresseServeur"],
    );
    const { ongletCollecte, pointOnglet, depot } = await chrome.storage.session.get(
      ["ongletCollecte", "pointOnglet", "depot"],
    );
    if (!jeton) return;
    const origine = normaliserOrigine(adresseServeur);
    if (depot) {
      if (normaliserOrigine(depot.origine) !== origine) {
        await chrome.storage.session.remove("depot");
      } else if (!await livrer(origine, jeton, depot)) return;
    }
    if (suspendu) return;
    const reponse = await appelerApi(origine, `/enseignes/${drive.enseigneId}/prendre`, jeton);
    if (!reponse.ok) return;
    const tache = await reponse.json();
    if (!tache) return;
    const point = tache.point;
    if (!point || tache.drive_id !== drive.enseigneId + "-" + point.id
        || !siteDuDrive(point.accueil) || !/^\d+$/.test(point.reference)) return;
    let resultat;
    try {
      resultat = await relever(
        await ouvrirOnglet(ongletCollecte), tache.requete, point, pointOnglet !== tache.drive_id,
      );
    } catch {
      resultat = { erreur: "page_inattendue" };
    }
    if (resultat.erreur) await chrome.storage.session.remove("pointOnglet");
    else await chrome.storage.session.set({ pointOnglet: tache.drive_id });
    const message = {
      id: tache.id,
      origine,
      depot: {
        drive_id: tache.drive_id,
        bail: tache.bail,
        etat: resultat.erreur ? "echec" : resultat.etat,
        ...resultat,
      },
    };
    await chrome.storage.session.set({ depot: message });
    await livrer(origine, jeton, message);
  } catch {
    // Serveur temporairement inaccessible. Réessayer au prochain réveil.
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
  if (ongletCollecte === tabId) await chrome.storage.session.remove(["ongletCollecte", "pointOnglet"]);
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
