-- Cache des prix collectés (lot 4). Clé : enseigne + magasin + recherche ("ean:<ean>" ou "texte:<recherche>").
CREATE TABLE IF NOT EXISTS cache_prix (
    cle TEXT PRIMARY KEY,
    enseigne TEXT NOT NULL,
    magasin_id TEXT NOT NULL,
    recherche TEXT NOT NULL,
    contenu_json TEXT NOT NULL,      -- Prix sérialisé (Prix.model_dump_json())
    source TEXT NOT NULL,
    releve_le TEXT NOT NULL,         -- ISO 8601, UTC
    expire_le TEXT NOT NULL          -- ISO 8601, UTC
);

CREATE INDEX IF NOT EXISTS idx_cache_prix_magasin ON cache_prix (magasin_id);
