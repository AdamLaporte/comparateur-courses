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

CREATE TABLE IF NOT EXISTS lieu_trajet (
    id INTEGER PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateur (id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    adresse TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    mode TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS lieu_trajet_utilisateur ON lieu_trajet (utilisateur_id);

CREATE TABLE IF NOT EXISTS comparaison_cagnotte (
    id TEXT PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateur (id) ON DELETE CASCADE,
    ecarts_json TEXT NOT NULL,
    montant_centimes INTEGER,
    cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS comparaison_cagnotte_utilisateur
    ON comparaison_cagnotte (utilisateur_id);
