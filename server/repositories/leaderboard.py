from server.db import connection

_SIMPLE_COLS = {
    "base_level": "c.base_level",
    "job_level": "c.job_level",
    "zeny": "c.zeny",
}

_BASE_FROM = "FROM characters c JOIN accounts a ON a.id = c.account_id"


def top(by: str, limit: int = 50) -> list[dict]:
    if by in _SIMPLE_COLS:
        col = _SIMPLE_COLS[by]
        sql = (
            f"SELECT c.name AS character_name, a.username AS account, "
            f"{col} AS value {_BASE_FROM} ORDER BY value DESC, c.id ASC LIMIT ?"
        )
    elif by == "cards":
        sql = (
            f"SELECT c.name AS character_name, a.username AS account, "
            f"COUNT(DISTINCT ci.item_id) AS value {_BASE_FROM} "
            f"JOIN character_items ci ON ci.character_id = c.id "
            f"AND ci.qty > 0 AND ci.item_id LIKE '%_card' "
            f"GROUP BY c.id ORDER BY value DESC, c.id ASC LIMIT ?"
        )
    elif by == "refine":
        sql = (
            f"SELECT c.name AS character_name, a.username AS account, "
            f"MAX(ce.refine) AS value {_BASE_FROM} "
            f"JOIN character_equipment ce ON ce.character_id = c.id "
            f"GROUP BY c.id ORDER BY value DESC, c.id ASC LIMIT ?"
        )
    else:
        raise ValueError(f"未知的排行榜依據：{by}")

    with connection.get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
