import secrets
from datetime import datetime, timezone

from server.db import connection

# 去掉易混淆字元（I O 0 1），使用者要手動輸入邀請碼
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class InviteError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_code() -> str:
    return "-".join(
        "".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3)
    )


def create_invite() -> str:
    code = generate_code()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO invite_codes (code, created_at) VALUES (?, ?)",
            (code, _now()),
        )
    return code


def is_available(code: str) -> bool:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT used_by_account FROM invite_codes WHERE code = ?", (code,)
        ).fetchone()
    return row is not None and row["used_by_account"] is None


def consume_invite(code: str, account_id: int) -> None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT used_by_account FROM invite_codes WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            raise InviteError("邀請碼不存在")
        if row["used_by_account"] is not None:
            raise InviteError("邀請碼已被使用")
        conn.execute(
            "UPDATE invite_codes SET used_by_account = ?, used_at = ? WHERE code = ?",
            (account_id, _now(), code),
        )
