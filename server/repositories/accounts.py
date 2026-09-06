import sqlite3
from datetime import datetime, timezone

from server.db import connection


class UsernameTakenError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_account(username: str, password_hash: str) -> int:
    try:
        with connection.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise UsernameTakenError(username) from exc


def get_account_by_username(username: str):
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()


def get_account(account_id: int):
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
