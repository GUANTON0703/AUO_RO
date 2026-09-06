import sqlite3
from contextlib import contextmanager
from pathlib import Path

_db_path: str | None = None

_SCHEMA = Path(__file__).with_name("schema.sql")


def configure(db_path: str) -> None:
    global _db_path
    _db_path = db_path


def _require_path() -> str:
    if _db_path is None:
        raise RuntimeError("connection.configure(db_path) 尚未呼叫")
    return _db_path


@contextmanager
def get_connection():
    conn = sqlite3.connect(_require_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ddl = _SCHEMA.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(ddl)
