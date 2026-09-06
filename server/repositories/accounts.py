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


def register_with_invite(username: str, password_hash: str, invite_code: str) -> int:
    """在單一 IMMEDIATE 交易內驗證邀請碼、建立帳號、消耗邀請碼。
    任一步失敗整筆 rollback，邀請碼不會被消耗掉。"""
    from server.auth.invites import InviteError

    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT used_by_account FROM invite_codes WHERE code = ?", (invite_code,)
        ).fetchone()
        if row is None or row["used_by_account"] is not None:
            raise InviteError("邀請碼無效或已被使用")
        try:
            cur = conn.execute(
                "INSERT INTO accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise UsernameTakenError(username) from exc
        account_id = cur.lastrowid
        conn.execute(
            "UPDATE invite_codes SET used_by_account = ?, used_at = ? WHERE code = ?",
            (account_id, _now(), invite_code),
        )
        return account_id


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
