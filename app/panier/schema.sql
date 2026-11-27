-- Lignes de la liste de courses. Propriétaire : "session:<uuid>" sans compte, "utilisateur:<id>" avec.
CREATE TABLE IF NOT EXISTS ligne_liste (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proprietaire TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('produit', 'equivalent', 'inexistant')),
    ean TEXT,
    recherche TEXT NOT NULL,
    libelle TEXT NOT NULL,
    quantite INTEGER NOT NULL DEFAULT 1 CHECK (quantite BETWEEN 1 AND 99),
    cree_le TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ligne_liste_proprietaire ON ligne_liste (proprietaire);

CREATE TABLE IF NOT EXISTS liste_courses (
    cle TEXT PRIMARY KEY,
    proprietaire TEXT NOT NULL,
    nom TEXT NOT NULL CHECK (length(nom) BETWEEN 1 AND 60)
);

CREATE INDEX IF NOT EXISTS idx_liste_courses_proprietaire ON liste_courses (proprietaire);
