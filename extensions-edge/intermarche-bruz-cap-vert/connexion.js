export const origineLocale = "http://127.0.0.1:8000";

export function normaliserOrigine(adresse) {
  const origine = (adresse || origineLocale).trim().toLowerCase().replace(/\/$/, "");
  if (origine === origineLocale || /^https:\/\/(?:[a-z0-9][a-z0-9-]*\.){2}ts\.net$/.test(origine)) {
    return origine;
  }
  throw new Error("Adresse locale ou HTTPS Tailscale attendue.");
}

export function appelerApi(origine, route, jeton, corps) {
  return fetch(normaliserOrigine(origine) + "/api/drives" + route, {
    method: "POST",
    credentials: "omit",
    redirect: "error",
    signal: AbortSignal.timeout(5000),
    headers: { "X-Drives-Jeton": jeton, "Content-Type": "application/json" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
}
