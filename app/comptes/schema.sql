-- Comptes et favoris (lot 2). Tout le site reste utilisable sans compte.
CREATE TABLE IF NOT EXISTS utilisateur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe_hash TEXT NOT NULL,          -- argon2 (pwdlib), jamais le mot de passe en clair
    cree_le TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS adresse_favorite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateur (id) ON DELETE CASCADE,
    libelle TEXT NOT NULL,                    -- ex. « Résidence », « Parents »
    code_postal TEXT NOT NULL,
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS article_favori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateur (id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('produit', 'equivalent')),
    ean TEXT,
    recherche TEXT NOT NULL,
    libelle TEXT NOT NULL
);
