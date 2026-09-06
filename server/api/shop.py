from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.db import connection
from server.repositories import characters as characters_repo

router = APIRouter(prefix="/api/shop", tags=["shop"])

_content = load_content()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_character(account_id: int):
    rows = characters_repo.list_for_account(account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="沒有角色")
    return rows[0]


class BuyRequest(BaseModel):
    item_id: str
    qty: int = Field(default=1, ge=1)


class SellRequest(BaseModel):
    item_id: str | None = None
    qty: int = Field(default=1, ge=1)
    equipment_instance_id: int | None = None


@router.get("")
def list_shop(account_id: CurrentAccount):
    _current_character(account_id)
    items = [
        {"id": i.id, "name": i.name, "price": i.npc_buy, "kind": i.kind}
        for i in _content.items.values()
        if i.npc_buy is not None
    ]
    equipment = [
        {"id": e.id, "name": e.name, "price": e.npc_buy, "slot": e.slot}
        for e in _content.equipment.values()
        if e.npc_buy is not None
    ]
    return {"items": items, "equipment": equipment}


@router.post("/buy")
def buy(body: BuyRequest, account_id: CurrentAccount):
    char = _current_character(account_id)
    item = _content.items.get(body.item_id)
    eq = _content.equipment.get(body.item_id)

    if item is not None and item.npc_buy is not None:
        price, is_equipment = item.npc_buy, False
    elif eq is not None and eq.npc_buy is not None:
        price, is_equipment = eq.npc_buy, True
    else:
        raise HTTPException(status_code=400, detail="此商品無法購買")

    total = price * body.qty
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT zeny FROM characters WHERE id = ?", (char["id"],)
        ).fetchone()
        if row["zeny"] < total:
            raise HTTPException(status_code=400, detail="Zeny 不足")
        conn.execute(
            "UPDATE characters SET zeny = zeny - ? WHERE id = ?", (total, char["id"])
        )
        if is_equipment:
            for _ in range(body.qty):
                conn.execute(
                    "INSERT INTO character_equipment "
                    "(character_id, equipment_id, refine, acquired_at) VALUES (?, ?, 0, ?)",
                    (char["id"], body.item_id, _now_iso()),
                )
        else:
            conn.execute(
                "INSERT INTO character_items (character_id, item_id, qty) VALUES (?, ?, ?) "
                "ON CONFLICT(character_id, item_id) DO UPDATE SET qty = qty + excluded.qty",
                (char["id"], body.item_id, body.qty),
            )
    return {"ok": True, "spent": total}


@router.post("/sell")
def sell(body: SellRequest, account_id: CurrentAccount):
    char = _current_character(account_id)

    if body.equipment_instance_id is not None:
        with connection.transaction() as conn:
            inst = conn.execute(
                "SELECT * FROM character_equipment WHERE id = ?",
                (body.equipment_instance_id,),
            ).fetchone()
            if inst is None or inst["character_id"] != char["id"]:
                raise HTTPException(status_code=404, detail="找不到裝備")
            if inst["equipped_slot"] is not None:
                raise HTTPException(status_code=400, detail="裝備中的道具無法賣出")
            eq = _content.equipment.get(inst["equipment_id"])
            price = eq.npc_sell if eq else 0
            conn.execute(
                "DELETE FROM character_equipment WHERE id = ?",
                (body.equipment_instance_id,),
            )
            conn.execute(
                "UPDATE characters SET zeny = zeny + ? WHERE id = ?", (price, char["id"])
            )
        return {"ok": True, "gained": price}

    if body.item_id is None:
        raise HTTPException(status_code=400, detail="需指定 item_id 或 equipment_instance_id")
    item = _content.items.get(body.item_id)
    if item is None:
        raise HTTPException(status_code=400, detail="道具不存在")
    gained = item.npc_sell * body.qty
    with connection.transaction() as conn:
        row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (char["id"], body.item_id),
        ).fetchone()
        if not row or row["qty"] < body.qty:
            raise HTTPException(status_code=400, detail="背包數量不足")
        conn.execute(
            "UPDATE character_items SET qty = qty - ? WHERE character_id = ? AND item_id = ?",
            (body.qty, char["id"], body.item_id),
        )
        conn.execute(
            "UPDATE characters SET zeny = zeny + ? WHERE id = ?", (gained, char["id"])
        )
    return {"ok": True, "gained": gained}
