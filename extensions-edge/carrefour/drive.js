export const drive = {
  enseigne: "Carrefour",
  enseigneId: "carrefour",
  domains: ["carrefour.fr"],
};

export function urlRecherche(accueil, requete, selectionner = false) {
  const destination = new URL("/s", accueil);
  destination.searchParams.set("q", requete);
  if (!selectionner) return destination.href;

  const selection = new URL(accueil);
  selection.searchParams.set("redirect", destination.pathname + destination.search);
  return selection.href;
}
