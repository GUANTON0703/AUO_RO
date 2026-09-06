import sqlite3
from datetime import datetime, timezone

from server.db import connection


class GuildError(Exception):
    pass


class GuildNameTaken(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _membership(conn, account_id: int):
    return conn.execute(
        "SELECT * FROM guild_members WHERE account_id = ?", (account_id,)
    ).fetchone()


def create(account_id: int, character_name: str, name: str) -> dict:
    with connection.transaction() as conn:
        if _membership(conn, account_id) is not None:
            raise GuildError("你已經在一個公會裡")
        try:
            cur = conn.execute(
                "INSERT INTO guilds (name, leader_account_id, created_at) VALUES (?, ?, ?)",
                (name, account_id, _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise GuildNameTaken(name) from exc
        guild_id = cur.lastrowid
        conn.execute(
            "INSERT INTO guild_members (guild_id, account_id, character_name, role, joined_at) "
            "VALUES (?, ?, ?, 'leader', ?)",
            (guild_id, account_id, character_name, _now()),
        )
        return {"id": guild_id, "name": name}


def join(account_id: int, character_name: str, guild_id: int) -> None:
    with connection.transaction() as conn:
        g = conn.execute("SELECT 1 FROM guilds WHERE id = ?", (guild_id,)).fetchone()
        if g is None:
            raise GuildError("公會不存在")
        if _membership(conn, account_id) is not None:
            raise GuildError("你已經在一個公會裡")
        conn.execute(
            "INSERT INTO guild_members (guild_id, account_id, character_name, role, joined_at) "
            "VALUES (?, ?, ?, 'member', ?)",
            (guild_id, account_id, character_name, _now()),
        )


def leave(account_id: int) -> None:
    with connection.transaction() as conn:
        m = _membership(conn, account_id)
        if m is None:
            raise GuildError("你不在任何公會")
        guild_id = m["guild_id"]
        conn.execute(
            "DELETE FROM guild_members WHERE account_id = ?", (account_id,)
        )
        if m["role"] != "leader":
            return
        heir = conn.execute(
            "SELECT account_id FROM guild_members WHERE guild_id = ? "
            "ORDER BY joined_at ASC, rowid ASC LIMIT 1",
            (guild_id,),
        ).fetchone()
        if heir is None:
            conn.execute("DELETE FROM guilds WHERE id = ?", (guild_id,))
            return
        conn.execute(
            "UPDATE guild_members SET role = 'leader' WHERE guild_id = ? AND account_id = ?",
            (guild_id, heir["account_id"]),
        )
        conn.execute(
            "UPDATE guilds SET leader_account_id = ? WHERE id = ?",
            (heir["account_id"], guild_id),
        )


def mine(account_id: int) -> dict | None:
    with connection.get_connection() as conn:
        m = _membership(conn, account_id)
        if m is None:
            return None
        guild = conn.execute(
            "SELECT * FROM guilds WHERE id = ?", (m["guild_id"],)
        ).fetchone()
        members = [
            {
                "account_id": r["account_id"],
                "character_name": r["character_name"],
                "role": r["role"],
                "joined_at": r["joined_at"],
            }
            for r in conn.execute(
                "SELECT * FROM guild_members WHERE guild_id = ? ORDER BY joined_at ASC, rowid ASC",
                (m["guild_id"],),
            ).fetchall()
        ]
        return {"id": guild["id"], "name": guild["name"], "members": members}


def list_all() -> list[dict]:
    with connection.get_connection() as conn:
        return [
            {"id": r["id"], "name": r["name"], "member_count": r["member_count"]}
            for r in conn.execute(
                """
                SELECT g.id, g.name, COUNT(m.account_id) AS member_count
                FROM guilds g LEFT JOIN guild_members m ON m.guild_id = g.id
                GROUP BY g.id ORDER BY g.id
                """
            ).fetchall()
        ]
