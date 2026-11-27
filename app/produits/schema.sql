-- Référentiel produits (lot 4) : produits vus dans les recherches Open Food Facts.
CREATE TABLE IF NOT EXISTS produit (
    ean TEXT PRIMARY KEY,
    libelle TEXT NOT NULL,
    marque TEXT,
    quantite TEXT,                 -- ex. "400 g"
    source TEXT NOT NULL,          -- "open_food_facts"
    maj_le TEXT NOT NULL           -- ISO 8601, UTC
);
