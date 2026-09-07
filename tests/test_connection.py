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
    assert 1 in versions
    assert "hunt_kills" in cols   # migration 1 加的欄位在
