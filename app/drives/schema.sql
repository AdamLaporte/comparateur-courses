CREATE TABLE IF NOT EXISTS drive_reference (
    drive_id TEXT NOT NULL,
    cle TEXT NOT NULL,
    PRIMARY KEY (drive_id, cle)
);

CREATE TABLE IF NOT EXISTS drive_observation (
    id INTEGER PRIMARY KEY,
    drive_id TEXT NOT NULL,
    reference TEXT NOT NULL,
    date_tri TEXT NOT NULL,
    releve_le TEXT NOT NULL,
    texte TEXT NOT NULL,
    ean TEXT NOT NULL,
    contenu TEXT NOT NULL,
    UNIQUE (drive_id, reference, date_tri, contenu),
    FOREIGN KEY (drive_id, reference) REFERENCES drive_reference (drive_id, cle)
);

CREATE INDEX IF NOT EXISTS drive_observation_reference
    ON drive_observation (drive_id, reference, date_tri DESC, id DESC);
CREATE INDEX IF NOT EXISTS drive_observation_ean ON drive_observation (drive_id, ean);

CREATE TABLE IF NOT EXISTS drive_collecteur (
    drive_id TEXT PRIMARY KEY,
    vu_le TEXT,
    pause_jusqua TEXT
);

CREATE TABLE IF NOT EXISTS drive_collecteur_enseigne (
    enseigne TEXT PRIMARY KEY,
    vu_le TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drive_tache (
    id INTEGER PRIMARY KEY,
    drive_id TEXT NOT NULL,
    cle TEXT NOT NULL,
    requete TEXT NOT NULL,
    etat TEXT NOT NULL CHECK (etat IN ('attente', 'cours', 'succes', 'vide', 'echec')),
    expire_le TEXT NOT NULL,
    bail TEXT,
    termine_le TEXT,
    erreur TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS drive_tache_active
    ON drive_tache (drive_id, cle) WHERE etat IN ('attente', 'cours');
CREATE INDEX IF NOT EXISTS drive_tache_recherche ON drive_tache (drive_id, cle, id DESC);

CREATE TABLE IF NOT EXISTS drive_attribution (
    tache_id INTEGER PRIMARY KEY REFERENCES drive_tache (id),
    collecteur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drive_tache_observation (
    tache_id INTEGER REFERENCES drive_tache (id),
    observation_id INTEGER REFERENCES drive_observation (id),
    PRIMARY KEY (tache_id, observation_id)
);
