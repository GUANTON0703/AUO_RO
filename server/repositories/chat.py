from datetime import datetime, timezone

from server.db import connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def post(channel: str, account_id: int | None, character_name: str, text: str) -> dict:
    with connection.get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (channel, account_id, character_name, text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (channel, account_id, character_name, text, _now()),
        )
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def recent(channel: str, limit: int = 30) -> list[dict]:
    """最新的 limit 則（照時間正序回傳），給只想看近況的精簡視圖用。"""
    with connection.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE channel = ? ORDER BY id DESC LIMIT ?",
            (channel, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def dm_channel(a: int, b: int) -> str:
    lo, hi = sorted((a, b))
    return f"dm:{lo}:{hi}"


def dm_ids(channel: str) -> set[int] | None:
    parts = channel.split(":")
    if len(parts) != 3:
        return None
    try:
        return {int(parts[1]), int(parts[2])}
    except ValueError:
        return None


def dm_threads(account_id: int) -> list[dict]:
    """我參與的所有私訊頻道，各帶最後一則訊息，最新的在前。"""
    with connection.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.channel, m.character_name, m.text, m.created_at, m.id
            FROM chat_messages m
            JOIN (
                SELECT channel, MAX(id) AS mx FROM chat_messages
                WHERE channel LIKE 'dm:%' GROUP BY channel
            ) t ON t.channel = m.channel AND t.mx = m.id
            ORDER BY m.id DESC
            """
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        ids = dm_ids(r["channel"])
        if not ids or account_id not in ids:
            continue
        other = next(iter(ids - {account_id}), account_id)
        out.append({
            "channel": r["channel"], "other_account": other,
            "last_text": r["text"], "last_at": r["created_at"],
            "last_id": r["id"], "last_from": r["character_name"],
        })
    return out


def since(channel: str, after_id: int, limit: int = 100) -> list[dict]:
    with connection.get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE channel = ? AND id > ?
                ORDER BY id ASC LIMIT ?
                """,
                (channel, after_id, limit),
            ).fetchall()
        ]
