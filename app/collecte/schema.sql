-- Cache des prix collectés (lot 4). Clé : magasin + recherche ("<magasin_id>|ean:<ean>" ou "<magasin_id>|texte:<recherche>").
-- Le magasin_id commence par l'enseigne : la clé couvre donc enseigne + magasin + recherche.
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

-- Réponses brutes des services ouverts (Open Prices, Open Food Facts), pour limiter les appels et
-- garder une réponse à montrer si le service ne répond plus. Clé : "<service>:<requête>".
CREATE TABLE IF NOT EXISTS cache_reponse (
    cle TEXT PRIMARY KEY,
    contenu_json TEXT NOT NULL,
    recu_le TEXT NOT NULL            -- ISO 8601, UTC
);
