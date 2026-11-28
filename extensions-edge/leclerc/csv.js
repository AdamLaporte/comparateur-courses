export const columns = [
  "enseigne", "drive", "service_drive", "releve_le", "recherches", "ean", "produit", "marque", "format",
  "prix_eur", "prix_par_unite_eur", "unite", "achetable", "promos", "promos_json", "url",
  "adresse", "source", "rayon", "id_produit_source"
];

export function csv(rows) {
  function cell(value = "") {
    const text = String(value);
    const safeText = /^\s*[=+\-@\t\r]/.test(text) ? "'" + text : text;
    return '"' + safeText.replaceAll('"', '""') + '"';
  }
  return "\uFEFF" + [columns.join(";"), ...rows.map((row) => columns.map((key) => cell(row[key])).join(";"))]
    .join("\r\n") + "\r\n";
}

export function price(value) {
  const input = value.trim().replace(",", ".");
  if (!/^\d{1,6}(\.\d{1,2})?$/.test(input)) return null;
  return Number(input).toFixed(2);
}

export function validEan(value) {
  if (!/^(\d{8}|\d{12,14})$/.test(value)) return false;
  return [...value].reverse().reduce((total, digit, index) => total + Number(digit) * (index % 2 ? 3 : 1), 0) % 10 === 0;
}
