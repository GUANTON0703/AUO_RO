from server.db import connection


def test_init_db_creates_tables(tmp_path):
    db = tmp_path / "t.db"
    connection.configure(str(db))
    connection.init_db()
    with connection.get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    names = {r["name"] for r in rows}
    assert {"accounts", "invite_codes", "sessions", "characters"} <= names


def test_wal_and_foreign_keys(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_rows_are_dict_like(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("a", "h", "2026-01-01T00:00:00Z"),
        )
        row = conn.execute("SELECT * FROM accounts").fetchone()
    assert row["username"] == "a"


def test_commit_on_success_rollback_on_error(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    try:
        with connection.get_connection() as conn:
            conn.execute(
                "INSERT INTO accounts (username, password_hash, created_at) VALUES (?,?,?)",
                ("x", "h", "t"),
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with connection.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"] == 0


def test_migrations_recorded_and_idempotent(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    connection.init_db()   # 再跑一次不該重複套用或報錯
    with connection.get_connection() as conn:
        versions = {r[0] for r in conn.execute(
            "SELECT version FROM schema_migrations").fetchall()}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(characters)").fetchall()}
    assert {1, 2} <= versions
    assert "hunt_kills" in cols   # migration 1 加的欄位在


def test_migration_2_backfills_carried_points_for_second_jobbers(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (username, password_hash, created_at) VALUES (?,?,?)",
            ("a", "h", "t"),
        )
        aid = conn.execute("SELECT id FROM accounts").fetchone()["id"]
        for job, name in (("assassin", "老刺客"), ("thief", "新賊"), ("novice", "菜")):
            conn.execute(
                "INSERT INTO characters (account_id, name, job_id, location_map, created_at) "
                "VALUES (?,?,?,?,?)", (aid, name, job, "prontera_east_gate", "t"),
            )
        connection._migration_2(conn)   # 直接套一次（migration runner 只會跑一次）
        got = {r["name"]: r["skill_points"]
               for r in conn.execute("SELECT name, skill_points FROM characters")}
    assert got["老刺客"] == 39   # 二轉角色補上 carried
    assert got["新賊"] == 0      # 一轉角色不動
    assert got["菜"] == 0


def test_migration_3_renames_learned_skill_ids(tmp_path):
    import json
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (username, password_hash, created_at) VALUES (?,?,?)",
            ("a", "h", "t"),
        )
        aid = conn.execute("SELECT id FROM accounts").fetchone()["id"]
        conn.execute(
            "INSERT INTO characters (account_id, name, job_id, location_map, created_at, "
            "learned_skills) VALUES (?,?,?,?,?,?)",
            (aid, "騎士", "knight", "prontera_east_gate", "t",
             json.dumps({"shield_charge": 3, "bash": 5})),
        )
        conn.execute(
            "INSERT INTO characters (account_id, name, job_id, location_map, created_at, "
            "learned_skills) VALUES (?,?,?,?,?,?)",
            (aid, "沒學的", "knight", "prontera_east_gate", "t", json.dumps({"bash": 1})),
        )
        conn.execute(
            "INSERT INTO characters (account_id, name, job_id, location_map, created_at, "
            "learned_skills) VALUES (?,?,?,?,?,?)",
            (aid, "巫師", "wizard", "prontera_east_gate", "t",
             json.dumps({"frost_armor": 2})),
        )
        connection._migration_3(conn)
        connection._migration_4(conn)
        got = {r["name"]: json.loads(r["learned_skills"])
               for r in conn.execute("SELECT name, learned_skills FROM characters")}
    assert got["騎士"] == {"counter_attack": 3, "bash": 5}
    assert got["沒學的"] == {"bash": 1}
    assert got["巫師"] == {"frost_nova": 2}
