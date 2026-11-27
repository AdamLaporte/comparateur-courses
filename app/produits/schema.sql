-- Référentiel produits : uniquement des données réelles, vues dans les recherches Open Food Facts ou
-- relevées sur un drive par les extensions (jamais le catalogue fictif).
CREATE TABLE IF NOT EXISTS produit (
    ean TEXT PRIMARY KEY,
    libelle TEXT NOT NULL,
    marque TEXT,
    quantite TEXT,                 -- ex. "400 g"
    source TEXT NOT NULL,          -- "open_food_facts" ou "drive:<drive_id>"
    maj_le TEXT NOT NULL           -- ISO 8601, UTC
);
