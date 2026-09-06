import json
from datetime import datetime, timezone

from server.db import connection


class StorageError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_storage(account_id: int) -> dict:
    with connection.get_connection() as conn:
        items = {
            r["item_id"]: r["qty"]
            for r in conn.execute(
                "SELECT item_id, qty FROM account_items WHERE account_id = ? AND qty > 0",
                (account_id,),
            ).fetchall()
        }
        equipment = [
            {
                "id": r["id"],
                "equipment_id": r["equipment_id"],
                "refine": r["refine"],
                "card_ids": json.loads(r["card_ids"]),
            }
            for r in conn.execute(
                "SELECT * FROM account_equipment WHERE account_id = ? ORDER BY id",
                (account_id,),
            ).fetchall()
        ]
    return {"items": items, "equipment": equipment}


def deposit_item(account_id: int, character_id: int, item_id: str, qty: int) -> None:
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (character_id, item_id),
        ).fetchone()
        if not row or row["qty"] < qty:
            raise StorageError("背包數量不足")
        conn.execute(
            "UPDATE character_items SET qty = qty - ? WHERE character_id = ? AND item_id = ?",
            (qty, character_id, item_id),
        )
        conn.execute(
            "INSERT INTO account_items (account_id, item_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(account_id, item_id) DO UPDATE SET qty = qty + excluded.qty",
            (account_id, item_id, qty),
        )


def withdraw_item(account_id: int, character_id: int, item_id: str, qty: int) -> None:
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT qty FROM account_items WHERE account_id = ? AND item_id = ?",
            (account_id, item_id),
        ).fetchone()
        if not row or row["qty"] < qty:
            raise StorageError("倉庫數量不足")
        conn.execute(
            "UPDATE account_items SET qty = qty - ? WHERE account_id = ? AND item_id = ?",
            (qty, account_id, item_id),
        )
        conn.execute(
            "INSERT INTO character_items (character_id, item_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(character_id, item_id) DO UPDATE SET qty = qty + excluded.qty",
            (character_id, item_id, qty),
        )


def deposit_equipment(account_id: int, character_id: int, instance_id: int) -> None:
    with connection.transaction() as conn:
        inst = conn.execute(
            "SELECT * FROM character_equipment WHERE id = ?", (instance_id,)
        ).fetchone()
        if inst is None or inst["character_id"] != character_id:
            raise StorageError("找不到裝備")
        if inst["equipped_slot"] is not None:
            raise StorageError("裝備中的道具無法存入")
        conn.execute("DELETE FROM character_equipment WHERE id = ?", (instance_id,))
        conn.execute(
            "INSERT INTO account_equipment "
            "(account_id, equipment_id, refine, card_ids, acquired_at) VALUES (?, ?, ?, ?, ?)",
            (account_id, inst["equipment_id"], inst["refine"], inst["card_ids"], _now()),
        )


def withdraw_equipment(account_id: int, character_id: int, storage_id: int) -> None:
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT * FROM account_equipment WHERE id = ?", (storage_id,)
        ).fetchone()
        if row is None or row["account_id"] != account_id:
            raise StorageError("找不到裝備")
        conn.execute("DELETE FROM account_equipment WHERE id = ?", (storage_id,))
        conn.execute(
            "INSERT INTO character_equipment "
            "(character_id, equipment_id, refine, equipped_slot, card_ids, acquired_at) "
            "VALUES (?, ?, ?, NULL, ?, ?)",
            (character_id, row["equipment_id"], row["refine"], row["card_ids"], _now()),
        )
