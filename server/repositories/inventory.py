import json
from datetime import datetime, timezone

from server.content import load_content
from server.db import connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_item(character_id: int, item_id: str, qty: int) -> None:
    with connection.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO character_items (character_id, item_id, qty)
            VALUES (?, ?, ?)
            ON CONFLICT(character_id, item_id)
            DO UPDATE SET qty = qty + excluded.qty
            """,
            (character_id, item_id, qty),
        )


def item_qty(character_id: int, item_id: str) -> int:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (character_id, item_id),
        ).fetchone()
        return row["qty"] if row else 0


def consume_item(character_id: int, item_id: str, qty: int) -> bool:
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (character_id, item_id),
        ).fetchone()
        have = row["qty"] if row else 0
        if have < qty:
            return False
        conn.execute(
            "UPDATE character_items SET qty = qty - ? WHERE character_id = ? AND item_id = ?",
            (qty, character_id, item_id),
        )
        return True


def add_equipment(character_id: int, equipment_id: str, refine: int = 0) -> int:
    with connection.get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO character_equipment
                (character_id, equipment_id, refine, acquired_at)
            VALUES (?, ?, ?, ?)
            """,
            (character_id, equipment_id, refine, _now()),
        )
        return cur.lastrowid


def _equip_dict(row) -> dict:
    return {
        "id": row["id"],
        "character_id": row["character_id"],
        "equipment_id": row["equipment_id"],
        "refine": row["refine"],
        "equipped_slot": row["equipped_slot"],
        "card_ids": json.loads(row["card_ids"]),
    }


def get_equipment(equipment_instance_id: int) -> dict | None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM character_equipment WHERE id = ?", (equipment_instance_id,)
        ).fetchone()
        return _equip_dict(row) if row else None


def update_equipment(equipment_instance_id: int, **fields) -> None:
    if not fields:
        return
    if "card_ids" in fields and not isinstance(fields["card_ids"], str):
        fields["card_ids"] = json.dumps(fields["card_ids"])
    cols = ", ".join(f"{k} = ?" for k in fields)
    with connection.get_connection() as conn:
        conn.execute(
            f"UPDATE character_equipment SET {cols} WHERE id = ?",
            (*fields.values(), equipment_instance_id),
        )


def list_inventory(character_id: int) -> dict:
    with connection.get_connection() as conn:
        items = {
            r["item_id"]: r["qty"]
            for r in conn.execute(
                "SELECT item_id, qty FROM character_items WHERE character_id = ? AND qty > 0",
                (character_id,),
            ).fetchall()
        }
        equipment = [
            _equip_dict(r)
            for r in conn.execute(
                "SELECT * FROM character_equipment WHERE character_id = ? ORDER BY id",
                (character_id,),
            ).fetchall()
        ]
    return {"items": items, "equipment": equipment}


def list_equipped(character_id: int) -> list[dict]:
    with connection.get_connection() as conn:
        return [
            _equip_dict(r)
            for r in conn.execute(
                "SELECT * FROM character_equipment "
                "WHERE character_id = ? AND equipped_slot IS NOT NULL ORDER BY id",
                (character_id,),
            ).fetchall()
        ]


def grant_starter_kit(character_id: int) -> None:
    add_equipment(character_id, "knife")
    add_item(character_id, "red_potion", 10)
    add_item(character_id, "fly_wing", 5)


def apply_drops(character_id: int, drops: dict) -> None:
    content = load_content()
    for item_id, qty in (drops or {}).items():
        if qty <= 0:
            continue
        if item_id in content.equipment:
            for _ in range(qty):
                add_equipment(character_id, item_id)
        else:
            add_item(character_id, item_id, qty)
