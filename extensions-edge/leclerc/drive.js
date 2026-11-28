export const drive = {
  enseigne: "E.Leclerc Drive",
  enseigneId: "leclerc",
  domains: ["leclercdrive.fr"],
};

export function urlRecherche(accueil, requete) {
  const destination = new URL(accueil);
  destination.pathname = destination.pathname.replace(/\.aspx\/?$/i, "/recherche.aspx");
  destination.searchParams.set("TexteRecherche", requete);
  return destination.href;
}
