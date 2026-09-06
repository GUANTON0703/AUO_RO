from datetime import datetime, timedelta, timezone

from server.db import connection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _available_at(character_id: int, mvp_id: str) -> datetime | None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT available_at FROM character_mvp_cooldowns "
            "WHERE character_id = ? AND mvp_id = ?",
            (character_id, mvp_id),
        ).fetchone()
    return _parse(row["available_at"]) if row else None


def is_available(character_id: int, mvp_id: str) -> bool:
    at = _available_at(character_id, mvp_id)
    return at is None or at <= _now()


def seconds_remaining(character_id: int, mvp_id: str) -> int:
    at = _available_at(character_id, mvp_id)
    if at is None:
        return 0
    return max(0, round((at - _now()).total_seconds()))


def set_cooldown(character_id: int, mvp_id: str, hours: float) -> None:
    available_at = (_now() + timedelta(hours=hours)).isoformat()
    with connection.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO character_mvp_cooldowns (character_id, mvp_id, available_at)
            VALUES (?, ?, ?)
            ON CONFLICT(character_id, mvp_id)
            DO UPDATE SET available_at = excluded.available_at
            """,
            (character_id, mvp_id, available_at),
        )


def all_cooldowns(character_id: int) -> dict[str, int]:
    with connection.get_connection() as conn:
        rows = conn.execute(
            "SELECT mvp_id, available_at FROM character_mvp_cooldowns WHERE character_id = ?",
            (character_id,),
        ).fetchall()
    now = _now()
    out: dict[str, int] = {}
    for r in rows:
        remain = round((_parse(r["available_at"]) - now).total_seconds())
        if remain > 0:
            out[r["mvp_id"]] = remain
    return out
