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


def get_character_by_name(name: str):
    with connection.get_connection() as conn:
        return conn.execute(
            "SELECT * FROM characters WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()


def names_for_accounts(account_ids: list[int]) -> dict[int, str]:
    """帳號 id -> 第一個角色名，用在交易顯示對方是誰。"""
    if not account_ids:
        return {}
    placeholders = ",".join("?" * len(account_ids))
    with connection.get_connection() as conn:
        rows = conn.execute(
            f"SELECT account_id, name FROM characters "
            f"WHERE account_id IN ({placeholders}) ORDER BY id",
            tuple(account_ids),
        ).fetchall()
    out: dict[int, str] = {}
    for r in rows:
        out.setdefault(r["account_id"], r["name"])
    return out


def set_hunt_state(character_id: int, *, map_id, monster_id, started_at,
                   last_settled_at, hp, sp) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            """
            UPDATE characters SET
                hunting_map_id = ?, hunting_monster_id = ?, hunt_started_at = ?,
                hunt_last_settled_at = ?, hunt_hp = ?, hunt_sp = ?,
                location_map = ?,
                hunt_kills = 0, hunt_base_exp = 0, hunt_job_exp = 0, hunt_zeny = 0,
                hunt_seconds = 0, hunt_loot = '{}',
                hunt_potions_used = 0, hunt_sp_potions_used = 0, hunt_potion_zeny_spent = 0
            WHERE id = ?
            """,
            (map_id, monster_id, started_at, last_settled_at, hp, sp, map_id,
             character_id),
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


def update_hunt_progress(character_id: int, *, hp, sp, last_settled_at,
                         kills=0, base_exp=0, job_exp=0, zeny=0, seconds=0.0,
                         potions_used=0, sp_potions_used=0, potion_zeny_spent=0) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET hunt_hp = ?, hunt_sp = ?, hunt_last_settled_at = ?, "
            "hunt_kills = hunt_kills + ?, hunt_base_exp = hunt_base_exp + ?, "
            "hunt_job_exp = hunt_job_exp + ?, hunt_zeny = hunt_zeny + ?, "
            "hunt_seconds = hunt_seconds + ?, "
            "hunt_potions_used = hunt_potions_used + ?, "
            "hunt_sp_potions_used = hunt_sp_potions_used + ?, "
            "hunt_potion_zeny_spent = hunt_potion_zeny_spent + ? WHERE id = ?",
            (hp, sp, last_settled_at, kills, base_exp, job_exp, zeny, seconds,
             potions_used, sp_potions_used, potion_zeny_spent, character_id),
        )


def add_hunt_potion_zeny_spent(character_id: int, amount: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET hunt_potion_zeny_spent = hunt_potion_zeny_spent + ? "
            "WHERE id = ?", (amount, character_id),
        )


def update_hunt_target(character_id: int, monster_id: str) -> None:
    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET hunting_monster_id = ? WHERE id = ?",
                     (monster_id, character_id))


def adjust_zeny(character_id: int, delta: int) -> int:
    """加減 Zeny，回傳結果。不會低於 0。"""
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET zeny = MAX(0, zeny + ?) WHERE id = ?",
            (delta, character_id),
        )
        return conn.execute(
            "SELECT zeny FROM characters WHERE id = ?", (character_id,)
        ).fetchone()["zeny"]


def spend_zeny(character_id: int, amount: int) -> bool:
    """原子扣款：餘額不足回傳 False，不會扣成負數。"""
    if amount <= 0:
        return True
    with connection.get_connection() as conn:
        cur = conn.execute(
            "UPDATE characters SET zeny = zeny - ? WHERE id = ? AND zeny >= ?",
            (amount, character_id, amount),
        )
        return cur.rowcount > 0


def set_craft_progress(character_id: int, level: int, exp: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET craft_level = ?, craft_exp = ? WHERE id = ?",
            (level, exp, character_id),
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


def reduce_hunt_loot(character_id: int, sold: dict) -> None:
    """自動賣掉的道具從本場撿到清單扣掉（顯示的是「留下的」）。"""
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT hunt_loot FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        loot = json.loads(row["hunt_loot"]) if row and row["hunt_loot"] else {}
        for k, v in (sold or {}).items():
            left = loot.get(k, 0) - v
            if left > 0:
                loot[k] = left
            else:
                loot.pop(k, None)
        conn.execute(
            "UPDATE characters SET hunt_loot = ? WHERE id = ?",
            (json.dumps(loot), character_id),
        )


def get_hunt_strategy(character_id: int) -> dict:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT hunt_strategy FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
    return json.loads(row["hunt_strategy"]) if row and row["hunt_strategy"] else {}


def set_hunt_strategy(character_id: int, strategy: dict) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET hunt_strategy = ? WHERE id = ?",
            (json.dumps(strategy), character_id),
        )


def get_active_potion_buffs(character_id: int) -> dict:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT active_potion_buffs FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
    return json.loads(row["active_potion_buffs"]) if row and row["active_potion_buffs"] else {}


def set_active_potion_buffs(character_id: int, buffs: dict) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE characters SET active_potion_buffs = ? WHERE id = ?",
            (json.dumps(buffs), character_id),
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


def set_job(character_id: int, job_id: str, job_level: int, job_exp: int,
            carried_skill_points: int | None = None) -> None:
    with connection.get_connection() as conn:
        if carried_skill_points is None:
            conn.execute(
                "UPDATE characters SET job_id = ?, job_level = ?, job_exp = ? WHERE id = ?",
                (job_id, job_level, job_exp, character_id),
            )
        else:
            conn.execute(
                "UPDATE characters SET job_id = ?, job_level = ?, job_exp = ?, "
                "skill_points = ? WHERE id = ?",
                (job_id, job_level, job_exp, carried_skill_points, character_id),
            )


def rebirth(character_id: int) -> None:
    """滿等重生：等級歸 1、屬性技能清空、設 is_rebirth；裝備 / 背包 / Zeny / 名字保留。"""
    with connection.get_connection() as conn:
        conn.execute(
            """
            UPDATE characters SET
                job_id = 'novice', base_level = 1, job_level = 1,
                base_exp = 0, job_exp = 0, skill_points = 0,
                learned_skills = '{}', is_rebirth = 1,
                stat_str = 1, stat_agi = 1, stat_vit = 1,
                stat_int = 1, stat_dex = 1, stat_luk = 1
            WHERE id = ?
            """,
            (character_id,),
        )


def delete_character(character_id: int, account_id: int) -> bool:
    with connection.transaction() as conn:
        owned = conn.execute(
            "SELECT 1 FROM characters WHERE id = ? AND account_id = ?",
            (character_id, account_id),
        ).fetchone()
        if not owned:
            return False
        conn.execute("DELETE FROM character_items WHERE character_id = ?", (character_id,))
        conn.execute("DELETE FROM character_equipment WHERE character_id = ?", (character_id,))
        conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        return True
