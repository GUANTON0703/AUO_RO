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


def init_db() -> None:
    ddl = _SCHEMA.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(ddl)
        account_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()
        }
        if "role" not in account_columns:
            conn.execute("ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'player'")
        character_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(characters)").fetchall()
        }
        for name, definition in (
            ("hunt_kills", "INTEGER NOT NULL DEFAULT 0"),
            ("hunt_base_exp", "INTEGER NOT NULL DEFAULT 0"),
            ("hunt_job_exp", "INTEGER NOT NULL DEFAULT 0"),
            ("hunt_zeny", "INTEGER NOT NULL DEFAULT 0"),
            ("hunt_seconds", "REAL NOT NULL DEFAULT 0"),
        ):
            if name not in character_columns:
                conn.execute(f"ALTER TABLE characters ADD COLUMN {name} {definition}")
