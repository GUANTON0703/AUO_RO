CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'player'
);

CREATE TABLE IF NOT EXISTS server_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL
);

INSERT OR IGNORE INTO server_settings (key, value) VALUES ('experience_multiplier', '1.0');
INSERT OR IGNORE INTO server_settings (key, value) VALUES ('drop_multiplier', '1.0');

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
    hunt_kills           INTEGER NOT NULL DEFAULT 0,
    hunt_base_exp        INTEGER NOT NULL DEFAULT 0,
    hunt_job_exp         INTEGER NOT NULL DEFAULT 0,
    hunt_zeny            INTEGER NOT NULL DEFAULT 0,
    hunt_seconds         REAL NOT NULL DEFAULT 0,
    hunt_pity            TEXT NOT NULL DEFAULT '{}',
    hunt_loot            TEXT NOT NULL DEFAULT '{}',
    learned_skills       TEXT NOT NULL DEFAULT '{}',
    equipped_items       TEXT NOT NULL DEFAULT '[]',
    socketed_cards       TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_characters_account ON characters(account_id);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);

CREATE TABLE IF NOT EXISTS character_items (
    character_id INTEGER NOT NULL REFERENCES characters(id),
    item_id      TEXT NOT NULL,
    qty          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, item_id)
);

CREATE TABLE IF NOT EXISTS character_equipment (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id  INTEGER NOT NULL REFERENCES characters(id),
    equipment_id  TEXT NOT NULL,
    refine        INTEGER NOT NULL DEFAULT 0,
    equipped_slot TEXT,
    card_ids      TEXT NOT NULL DEFAULT '[]',
    acquired_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_char_items ON character_items(character_id);
CREATE INDEX IF NOT EXISTS idx_char_equip ON character_equipment(character_id);

CREATE TABLE IF NOT EXISTS account_items (
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    item_id    TEXT NOT NULL,
    qty        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, item_id)
);
CREATE TABLE IF NOT EXISTS account_equipment (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    equipment_id TEXT NOT NULL,
    refine       INTEGER NOT NULL DEFAULT 0,
    card_ids     TEXT NOT NULL DEFAULT '[]',
    acquired_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_items ON account_items(account_id);
CREATE INDEX IF NOT EXISTS idx_account_equip ON account_equipment(account_id);

CREATE TABLE IF NOT EXISTS character_mvp_cooldowns (
    character_id INTEGER NOT NULL REFERENCES characters(id),
    mvp_id       TEXT NOT NULL,
    available_at TEXT NOT NULL,
    PRIMARY KEY (character_id, mvp_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    channel        TEXT NOT NULL,
    account_id     INTEGER REFERENCES accounts(id),
    character_name TEXT NOT NULL,
    text           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_channel ON chat_messages(channel, id);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account    INTEGER NOT NULL REFERENCES accounts(id),
    to_account      INTEGER NOT NULL REFERENCES accounts(id),
    status          TEXT NOT NULL DEFAULT 'open',
    from_confirmed  INTEGER NOT NULL DEFAULT 0,
    to_confirmed    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trade_items (
    trade_id      INTEGER NOT NULL REFERENCES trades(id),
    side          TEXT NOT NULL,
    item_id       TEXT,
    qty           INTEGER,
    equipment_id  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_trade_items ON trade_items(trade_id);

CREATE TABLE IF NOT EXISTS guilds (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL UNIQUE,
    leader_account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guild_members (
    guild_id       INTEGER NOT NULL REFERENCES guilds(id),
    account_id     INTEGER NOT NULL UNIQUE REFERENCES accounts(id),
    character_name TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'member',
    joined_at      TEXT NOT NULL
);
