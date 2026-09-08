import sqlite3
from contextlib import contextmanager
from pathlib import Path

_db_path: str | None = None

_SCHEMA = Path(__file__).with_name("schema.sql")

# 並發寫入者等鎖的上限（毫秒）。多個朋友同時打伺服器時，讓後到的寫入排隊而非直接報錯。
_BUSY_TIMEOUT_MS = 5000


def configure(db_path: str) -> None:
    global _db_path
    _db_path = db_path


def _require_path() -> str:
    if _db_path is None:
        raise RuntimeError("connection.configure(db_path) 尚未呼叫")
    return _db_path


def _prepare(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")


@contextmanager
def get_connection():
    conn = sqlite3.connect(_require_path())
    _prepare(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction():
    """BEGIN IMMEDIATE 交易：開頭就取 RESERVED 鎖，序列化競爭的寫入者。
    用在「先檢查再寫入」不能被並發插隊的地方（邀請碼消耗、角色數上限）。"""
    conn = sqlite3.connect(_require_path())
    conn.isolation_level = None  # 手動控制交易邊界
    _prepare(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()  # 沒有進行中的交易時是 no-op，不會蓋掉原始例外
        raise
    finally:
        conn.close()


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_col(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    if name not in _cols(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migration_1(conn: sqlite3.Connection) -> None:
    """v1 期間手寫的那批 ALTER，整理成第一個 migration。"""
    _add_col(conn, "accounts", "role", "TEXT NOT NULL DEFAULT 'player'")
    for name, definition in (
        ("hunt_kills", "INTEGER NOT NULL DEFAULT 0"),
        ("hunt_base_exp", "INTEGER NOT NULL DEFAULT 0"),
        ("hunt_job_exp", "INTEGER NOT NULL DEFAULT 0"),
        ("hunt_zeny", "INTEGER NOT NULL DEFAULT 0"),
        ("hunt_seconds", "REAL NOT NULL DEFAULT 0"),
    ):
        _add_col(conn, "characters", name, definition)
    conn.execute(
        "UPDATE character_equipment SET equipped_slot = 'accessory1' "
        "WHERE equipped_slot = 'accessory'"
    )


def _migration_2(conn: sqlite3.Connection) -> None:
    """轉職技能點修正之前二轉的角色：skill_points 欄位（= carried）還是 0，
    補上一轉練到門檻至少會有的點數（二轉門檻 40 → 39）。"""
    second_jobs = ("knight", "wizard", "hunter", "priest", "blacksmith", "assassin")
    placeholders = ",".join("?" * len(second_jobs))
    conn.execute(
        f"UPDATE characters SET skill_points = 39 "
        f"WHERE job_id IN ({placeholders}) AND skill_points = 0",
        second_jobs,
    )


# (version, callable(conn))。版本嚴格遞增，每個包在一個交易裡。
_MIGRATIONS: list[tuple[int, "callable"]] = [
    (1, _migration_1),
    (2, _migration_2),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    from datetime import datetime, timezone
    for version, fn in sorted(_MIGRATIONS):
        if version in done:
            continue
        fn(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )


def init_db() -> None:
    ddl = _SCHEMA.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(ddl)
        _apply_migrations(conn)
