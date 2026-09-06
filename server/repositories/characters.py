import sqlite3
from datetime import datetime, timezone

from server.db import connection


class NameTakenError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_character(account_id: int, name: str, location_map: str):
    try:
        with connection.get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO characters (account_id, name, location_map, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, name, location_map, _now()),
            )
            return conn.execute(
                "SELECT * FROM characters WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        raise NameTakenError(name) from exc


def create_within_limit(
    account_id: int, name: str, location_map: str, max_count: int
):
    """在單一 IMMEDIATE 交易內檢查角色數上限並建立。
    已達上限回傳 None；名稱重複丟 NameTakenError。"""
    with connection.transaction() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM characters WHERE account_id = ?", (account_id,)
        ).fetchone()["c"]
        if count >= max_count:
            return None
        try:
            cur = conn.execute(
                """
                INSERT INTO characters (account_id, name, location_map, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, name, location_map, _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise NameTakenError(name) from exc
        return conn.execute(
            "SELECT * FROM characters WHERE id = ?", (cur.lastrowid,)
        ).fetchone()


def list_for_account(account_id: int):
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT * FROM characters WHERE account_id = ? ORDER BY id", (account_id,)
        ).fetchall()


def count_for_account(account_id: int) -> int:
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM characters WHERE account_id = ?", (account_id,)
        ).fetchone()["c"]


def get_character(character_id: int):
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT * FROM characters WHERE id = ?", (character_id,)
        ).fetchone()


def delete_character(character_id: int, account_id: int) -> bool:
    with connection.get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM characters WHERE id = ? AND account_id = ?",
            (character_id, account_id),
        )
        return cur.rowcount > 0
