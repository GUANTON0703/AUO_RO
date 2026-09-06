CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_codes (
    code            TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    used_by_account INTEGER REFERENCES accounts(id),
    used_at         TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    name         TEXT NOT NULL UNIQUE,
    job_id       TEXT NOT NULL DEFAULT 'novice',
    base_level   INTEGER NOT NULL DEFAULT 1,
    job_level    INTEGER NOT NULL DEFAULT 1,
    base_exp     INTEGER NOT NULL DEFAULT 0,
    job_exp      INTEGER NOT NULL DEFAULT 0,
    stat_str     INTEGER NOT NULL DEFAULT 1,
    stat_agi     INTEGER NOT NULL DEFAULT 1,
    stat_vit     INTEGER NOT NULL DEFAULT 1,
    stat_int     INTEGER NOT NULL DEFAULT 1,
    stat_dex     INTEGER NOT NULL DEFAULT 1,
    stat_luk     INTEGER NOT NULL DEFAULT 1,
    stat_points  INTEGER NOT NULL DEFAULT 0,
    skill_points INTEGER NOT NULL DEFAULT 0,
    zeny         INTEGER NOT NULL DEFAULT 0,
    location_map TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    hunting_map_id       TEXT,
    hunting_monster_id   TEXT,
    hunt_started_at      TEXT,
    hunt_last_settled_at TEXT,
    hunt_hp              INTEGER,
    hunt_sp              INTEGER,
    hunt_pity            TEXT NOT NULL DEFAULT '{}',
    hunt_loot            TEXT NOT NULL DEFAULT '{}',
    learned_skills       TEXT NOT NULL DEFAULT '{}',
    equipped_items       TEXT NOT NULL DEFAULT '[]',
    socketed_cards       TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_characters_account ON characters(account_id);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
