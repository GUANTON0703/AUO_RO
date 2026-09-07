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


def table(trade_id: int) -> dict:
    with connection.get_connection() as conn:
        trade = _load(conn, trade_id)
        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM trade_items WHERE trade_id = ?", (trade_id,)
            ).fetchall()
        ]
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
