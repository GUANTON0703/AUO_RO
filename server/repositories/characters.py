import json
import sqlite3
from datetime import datetime, timezone

from server.db import connection

_STAT_COLS = ("str", "agi", "vit", "int", "dex", "luk")


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


def set_hunt_state(character_id: int, *, map_id, monster_id, started_at,
                   last_settled_at, hp, sp) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            """
            UPDATE characters SET
                hunting_map_id = ?, hunting_monster_id = ?, hunt_started_at = ?,
                hunt_last_settled_at = ?, hunt_hp = ?, hunt_sp = ?
            WHERE id = ?
            """,
            (map_id, monster_id, started_at, last_settled_at, hp, sp, character_id),
        )


def clear_hunt_state(character_id: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            """
            UPDATE characters SET
                hunting_map_id = NULL, hunting_monster_id = NULL,
                hunt_started_at = NULL, hunt_last_settled_at = NULL,
                hunt_hp = NULL, hunt_sp = NULL
            WHERE id = ?
            """,
            (character_id,),
        )


def update_hunt_progress(character_id: int, *, hp, sp, last_settled_at) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET hunt_hp = ?, hunt_sp = ?, hunt_last_settled_at = ? WHERE id = ?",
            (hp, sp, last_settled_at, character_id),
        )


def apply_progression(character_id: int, *, base_level: int, base_exp: int,
                      job_level: int, job_exp: int, zeny_delta: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            """
            UPDATE characters SET
                base_level = ?, base_exp = ?, job_level = ?, job_exp = ?,
                zeny = zeny + ?
            WHERE id = ?
            """,
            (base_level, base_exp, job_level, job_exp, zeny_delta, character_id),
        )


def merge_hunt_loot(character_id: int, loot_delta: dict, pity_replace: dict) -> None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT hunt_loot FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        loot = json.loads(row["hunt_loot"]) if row and row["hunt_loot"] else {}
        for k, v in (loot_delta or {}).items():
            loot[k] = loot.get(k, 0) + v
        conn.execute(
            "UPDATE characters SET hunt_loot = ?, hunt_pity = ? WHERE id = ?",
            (json.dumps(loot), json.dumps(pity_replace or {}), character_id),
        )


def set_learned_skills(character_id: int, learned: dict) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET learned_skills = ? WHERE id = ?",
            (json.dumps(learned or {}), character_id),
        )


def set_stats(character_id: int, stats: dict) -> None:
    cols = ", ".join(f"stat_{k} = ?" for k in _STAT_COLS)
    with connection.get_connection() as conn:
        conn.execute(
            f"UPDATE characters SET {cols} WHERE id = ?",
            (*(int(stats[k]) for k in _STAT_COLS), character_id),
        )


def set_job(character_id: int, job_id: str, job_level: int, job_exp: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET job_id = ?, job_level = ?, job_exp = ? WHERE id = ?",
            (job_id, job_level, job_exp, character_id),
        )


def delete_character(character_id: int, account_id: int) -> bool:
    with connection.get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM characters WHERE id = ? AND account_id = ?",
            (character_id, account_id),
        )
        return cur.rowcount > 0
