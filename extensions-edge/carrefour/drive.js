export const drive = {
  enseigne: "Carrefour",
  enseigneId: "carrefour",
  domains: ["carrefour.fr"],
};

export function urlRecherche(accueil, requete) {
  const destination = new URL("/s", accueil);
  destination.searchParams.set("q", requete);
  return destination.href;
}
