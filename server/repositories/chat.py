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
