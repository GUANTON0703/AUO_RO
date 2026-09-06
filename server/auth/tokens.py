import secrets
from datetime import datetime, timedelta, timezone

from server.db import connection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(account_id: int, ttl_hours: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(hours=ttl_hours)
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (token, account_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, account_id, now.isoformat(), expires.isoformat()),
        )
    return token


def resolve_token(token: str) -> int | None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT account_id, expires_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expires_at"]) <= _now():
        return None
    return row["account_id"]


def revoke_token(token: str) -> None:
    with connection.get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
