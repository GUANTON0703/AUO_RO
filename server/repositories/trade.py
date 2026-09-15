import json
from datetime import datetime, timezone

from server.db import connection


class TradeError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_char_id(conn, account_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM characters WHERE account_id = ? ORDER BY id LIMIT 1",
        (account_id,),
    ).fetchone()
    return row["id"] if row else None


def _load(conn, trade_id: int):
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        raise TradeError("交易不存在")
    return row


def _side_of(trade, account_id: int) -> str:
    if account_id == trade["from_account"]:
        return "from"
    if account_id == trade["to_account"]:
        return "to"
    raise TradeError("你不是這筆交易的參與者")


def offer(from_account: int, to_account: int) -> int:
    if from_account == to_account:
        raise TradeError("不能和自己交易")
    with connection.get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO trades (from_account, to_account, created_at) VALUES (?, ?, ?)",
            (from_account, to_account, _now()),
        )
        return cur.lastrowid


def put(trade_id, account_id, item_id=None, qty=None, equipment_id=None) -> None:
    with connection.transaction() as conn:
        trade = _load(conn, trade_id)
        if trade["status"] != "open":
            raise TradeError("交易已結束")
        side = _side_of(trade, account_id)
        char = _first_char_id(conn, account_id)
        if item_id is not None:
            if qty is None or qty < 1:
                raise TradeError("數量無效")
            owned_row = conn.execute(
                "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
                (char, item_id),
            ).fetchone()
            owned = owned_row["qty"] if owned_row else 0
            if qty > owned:
                raise TradeError("放上桌的數量超過持有量")
            conn.execute(
                "DELETE FROM trade_items WHERE trade_id = ? AND side = ? AND item_id = ?",
                (trade_id, side, item_id),
            )
            conn.execute(
                "INSERT INTO trade_items (trade_id, side, item_id, qty) VALUES (?, ?, ?, ?)",
                (trade_id, side, item_id, qty),
            )
        elif equipment_id is not None:
            r = conn.execute(
                "SELECT character_id FROM character_equipment WHERE id = ?",
                (equipment_id,),
            ).fetchone()
            if r is None or r["character_id"] != char:
                raise TradeError("這不是你的裝備")
            dup = conn.execute(
                "SELECT 1 FROM trade_items WHERE trade_id = ? AND equipment_id = ?",
                (trade_id, equipment_id),
            ).fetchone()
            if dup:
                raise TradeError("裝備已在桌上")
            conn.execute(
                "INSERT INTO trade_items (trade_id, side, equipment_id) VALUES (?, ?, ?)",
                (trade_id, side, equipment_id),
            )
        else:
            raise TradeError("需指定 item_id 或 equipment_id")
        conn.execute(
            "UPDATE trades SET from_confirmed = 0, to_confirmed = 0 WHERE id = ?",
            (trade_id,),
        )


def confirm(trade_id, account_id) -> dict:
    with connection.transaction() as conn:
        trade = _load(conn, trade_id)
        if trade["status"] != "open":
            raise TradeError("交易已結束")
        side = _side_of(trade, account_id)
        conn.execute(
            f"UPDATE trades SET {side}_confirmed = 1 WHERE id = ?", (trade_id,)
        )
        row = conn.execute(
            "SELECT from_confirmed, to_confirmed FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        if row["from_confirmed"] and row["to_confirmed"]:
            if _settle(conn, trade_id):
                return {"status": "done"}
            conn.execute(
                "UPDATE trades SET from_confirmed = 0, to_confirmed = 0 WHERE id = ?",
                (trade_id,),
            )
            return {"status": "open"}
        return {"status": "open"}


def cancel(trade_id, account_id) -> dict:
    with connection.transaction() as conn:
        trade = _load(conn, trade_id)
        _side_of(trade, account_id)
        if trade["status"] == "open":
            conn.execute(
                "UPDATE trades SET status = 'cancelled' WHERE id = ?", (trade_id,)
            )
        return {"status": "cancelled"}


def pending(account_id: int) -> list[dict]:
    with connection.get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM trades WHERE to_account = ? AND status = 'open' "
                "ORDER BY id DESC",
                (account_id,),
            ).fetchall()
        ]


def _resolve_items(conn, trade_id: int) -> list:
    """桌上每筆道具/裝備補上前端顯示要用的細節（裝備要 join character_equipment
    才拿得到真正的 equipment_id/精煉/插卡——trade_items.equipment_id 是那個
    角色裝備實例的 row id，不是圖鑑 id）。裝備還沒被拿走（交易還沒結算）時
    這個 join 一定找得到，結算完那筆已經轉移到對方名下、row id 不變一樣查得到。"""
    rows = conn.execute(
        "SELECT * FROM trade_items WHERE trade_id = ?", (trade_id,)
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        if d.get("equipment_id") is not None:
            eq = conn.execute(
                "SELECT equipment_id, refine, card_ids FROM character_equipment WHERE id = ?",
                (d["equipment_id"],),
            ).fetchone()
            if eq:
                d["catalog_equipment_id"] = eq["equipment_id"]
                d["refine"] = eq["refine"]
                d["card_ids"] = json.loads(eq["card_ids"]) if eq["card_ids"] else []
        items.append(d)
    return items


def table(trade_id: int) -> dict:
    with connection.get_connection() as conn:
        trade = _load(conn, trade_id)
        items = _resolve_items(conn, trade_id)
        return {
            "id": trade["id"],
            "status": trade["status"],
            "from_account": trade["from_account"],
            "to_account": trade["to_account"],
            "from_confirmed": trade["from_confirmed"],
            "to_confirmed": trade["to_confirmed"],
            "items": items,
        }


def _settle(conn, trade_id: int) -> bool:
    trade = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    from_char = _first_char_id(conn, trade["from_account"])
    to_char = _first_char_id(conn, trade["to_account"])
    if from_char is None or to_char is None:
        return False
    givers = {"from": from_char, "to": to_char}
    receivers = {"from": to_char, "to": from_char}
    items = conn.execute(
        "SELECT * FROM trade_items WHERE trade_id = ?", (trade_id,)
    ).fetchall()

    need: dict[tuple[int, str], int] = {}
    for it in items:
        giver = givers[it["side"]]
        if it["item_id"] is not None:
            need[(giver, it["item_id"])] = need.get((giver, it["item_id"]), 0) + it["qty"]
        else:
            r = conn.execute(
                "SELECT character_id FROM character_equipment WHERE id = ?",
                (it["equipment_id"],),
            ).fetchone()
            if r is None or r["character_id"] != giver:
                return False

    for (char, item_id), qty in need.items():
        row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (char, item_id),
        ).fetchone()
        if (row["qty"] if row else 0) < qty:
            return False

    for it in items:
        giver = givers[it["side"]]
        receiver = receivers[it["side"]]
        if it["item_id"] is not None:
            conn.execute(
                "UPDATE character_items SET qty = qty - ? "
                "WHERE character_id = ? AND item_id = ?",
                (it["qty"], giver, it["item_id"]),
            )
            conn.execute(
                """
                INSERT INTO character_items (character_id, item_id, qty)
                VALUES (?, ?, ?)
                ON CONFLICT(character_id, item_id)
                DO UPDATE SET qty = qty + excluded.qty
                """,
                (receiver, it["item_id"], it["qty"]),
            )
        else:
            conn.execute(
                "UPDATE character_equipment SET character_id = ?, equipped_slot = NULL "
                "WHERE id = ?",
                (receiver, it["equipment_id"]),
            )
    conn.execute("UPDATE trades SET status = 'done' WHERE id = ?", (trade_id,))
    return True
