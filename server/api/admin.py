from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import GMAccount
from server.content import load_content
from server.db import connection
from server.repositories import storage as storage_repo
from server.settlement.config import HuntConfig
from server.settlement.drops import effective_drop_rate, load_drop_rate_overrides

router = APIRouter(prefix="/api/admin", tags=["admin"])
_content = load_content()


class MoneyRequest(BaseModel):
    amount: int = Field(ge=-10_000_000, le=10_000_000)


class ExperienceRequest(BaseModel):
    base_exp: int = Field(ge=0, le=2_147_483_647)
    job_exp: int = Field(ge=0, le=2_147_483_647)


class MultipliersRequest(BaseModel):
    experience: float = Field(gt=0, le=100)
    drop: float = Field(gt=0, le=100)
    zeny: float | None = Field(default=None, gt=0, le=100)   # 省略 = 不動既有值


class HuntSettingsRequest(BaseModel):
    settle_floor_seconds: float = Field(ge=1, le=600)
    huntable_win_rate: float = Field(ge=0, le=1)


class AnnouncementRequest(BaseModel):
    text: str = Field(default="", max_length=500)


class DropRateRequest(BaseModel):
    source_id: str | None = Field(default=None, min_length=1, max_length=100)
    item_id: str = Field(min_length=1, max_length=100)
    rate: float = Field(ge=0, le=1)


class GrantItemRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    qty: int = Field(ge=1, le=100_000)
    refine: int = Field(default=0, ge=0, le=10)   # 只有裝備會用到


_SETTING_DEFAULTS = {
    "experience_multiplier": 1.0,
    "drop_multiplier": 1.0,
    "zeny_multiplier": 1.0,
    "settle_floor_seconds": HuntConfig().settle_floor_seconds,
    "huntable_win_rate": HuntConfig().huntable_win_rate,
}


def _character(character_id: int):
    with connection.get_connection() as conn:
        row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到角色")
    return row


def _validate_drop_item(item_id: str) -> None:
    if item_id not in _content.equipment and item_id not in _content.cards:
        raise HTTPException(status_code=404, detail="只支援裝備或卡片掉落率")


def _content_drop_rate(source_id: str | None, item_id: str,
                       *, allow_missing_source: bool = False) -> float:
    if source_id is not None:
        source = _content.monsters.get(source_id) or _content.mvps.get(source_id)
        if source is None:
            if allow_missing_source:
                return 0.0
            raise HTTPException(status_code=404, detail="找不到掉落來源")
        for drop in source.drops:
            if drop.item_id == item_id:
                return drop.rate
        card = _content.cards.get(item_id)
        if card and card.monster_id == source_id:
            return card.drop_rate
        return 0.0
    card = _content.cards.get(item_id)
    if card is not None:
        return card.drop_rate
    return 0.0


def _drop_rate_view(item_id: str, source_id: str | None = None,
                    *, allow_missing_source: bool = False) -> dict:
    _validate_drop_item(item_id)
    overrides = load_drop_rate_overrides()
    content_rate = _content_drop_rate(
        source_id, item_id, allow_missing_source=allow_missing_source
    )
    global_rate = overrides.global_rates.get(item_id)
    source_rate = (
        overrides.source_rates.get((source_id, item_id))
        if source_id is not None else None
    )
    return {
        "source_id": source_id,
        "item_id": item_id,
        "content_rate": content_rate,
        "global_rate": global_rate,
        "source_rate": source_rate,
        "effective_rate": effective_drop_rate(
            source_id, item_id, content_rate, overrides
        ),
    }


def _drop_rate_overrides() -> dict:
    with connection.get_connection() as conn:
        global_rows = conn.execute(
            "SELECT item_id, rate FROM global_drop_rates ORDER BY item_id"
        ).fetchall()
        source_rows = conn.execute(
            "SELECT source_id, item_id, rate FROM source_drop_rates "
            "ORDER BY source_id, item_id"
        ).fetchall()
    return {
        "global": [dict(row) for row in global_rows],
        "source": [dict(row) for row in source_rows],
    }


@router.post("/characters/{character_id}/money")
def adjust_money(character_id: int, body: MoneyRequest, _: GMAccount):
    _character(character_id)
    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET zeny = zeny + ? WHERE id = ?", (body.amount, character_id))
        return dict(conn.execute("SELECT id, zeny FROM characters WHERE id = ?", (character_id,)).fetchone())


@router.post("/characters/{character_id}/experience")
def set_experience(character_id: int, body: ExperienceRequest, _: GMAccount):
    _character(character_id)
    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET base_exp = ?, job_exp = ? WHERE id = ?", (body.base_exp, body.job_exp, character_id))
        return dict(conn.execute("SELECT id, base_exp, job_exp FROM characters WHERE id = ?", (character_id,)).fetchone())


@router.post("/characters/{character_id}/grant-item")
def grant_item(character_id: int, body: GrantItemRequest, _: GMAccount):
    """直接把道具/裝備塞進這個角色所屬帳號的倉庫（不是背包），玩家自己去倉庫領。"""
    row = _character(character_id)
    is_equipment = body.item_id in _content.equipment
    known = is_equipment or body.item_id in _content.items or body.item_id in _content.cards
    if not known:
        raise HTTPException(status_code=400, detail="道具不存在")
    account_id = row["account_id"]
    if is_equipment:
        for _ in range(body.qty):
            storage_repo.grant_equipment(account_id, body.item_id, body.refine)
    else:
        storage_repo.grant_item(account_id, body.item_id, body.qty)
    return {"account_id": account_id, "item_id": body.item_id, "qty": body.qty}


@router.get("/characters/search")
def search_characters(_: GMAccount, q: str = ""):
    """GM 用：用角色名找人（不限線上），回 account_id 給後續給錢/給經驗/塞倉庫用。"""
    q = q.strip()
    if not q:
        return []
    with connection.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS character_id, c.name, c.account_id, a.username,
                   c.base_level, c.job_level, c.zeny
            FROM characters c JOIN accounts a ON a.id = c.account_id
            WHERE c.name LIKE ? OR a.username LIKE ?
            ORDER BY c.id LIMIT 20
            """,
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    return [dict(row) for row in rows]


@router.put("/settings/multipliers")
def set_multipliers(body: MultipliersRequest, _: GMAccount):
    rows = [("experience_multiplier", str(body.experience)),
            ("drop_multiplier", str(body.drop))]
    if body.zeny is not None:
        rows.append(("zeny_multiplier", str(body.zeny)))
    with connection.transaction() as conn:
        conn.executemany(
            "INSERT INTO server_settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", rows)
        got = dict(conn.execute(
            "SELECT key, value FROM server_settings WHERE key = 'zeny_multiplier'"
        ).fetchall())
    zeny = float(got["zeny_multiplier"]) if "zeny_multiplier" in got \
        else HuntConfig().zeny_multiplier
    return {"experience": body.experience, "drop": body.drop, "zeny": zeny}


@router.get("/settings/drop-rates")
@router.get("/drop-rates")
def get_drop_rates(_: GMAccount, item_id: str | None = None,
                   source_id: str | None = None):
    if item_id is None:
        return _drop_rate_overrides()
    return _drop_rate_view(item_id, source_id)


@router.put("/settings/drop-rates")
@router.put("/drop-rates")
def set_drop_rate(body: DropRateRequest, _: GMAccount):
    _validate_drop_item(body.item_id)
    with connection.transaction() as conn:
        if body.source_id is None:
            conn.execute(
                "INSERT INTO global_drop_rates(item_id, rate) VALUES (?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET rate=excluded.rate",
                (body.item_id, body.rate),
            )
        else:
            source_rate = _content_drop_rate(body.source_id, body.item_id)
            card = _content.cards.get(body.item_id)
            card_source = card is not None and card.monster_id == body.source_id
            if source_rate == 0.0 and not card_source:
                raise HTTPException(status_code=404, detail="該來源不會掉落此裝備或卡片")
            conn.execute(
                "INSERT INTO source_drop_rates(source_id, item_id, rate) VALUES (?, ?, ?) "
                "ON CONFLICT(source_id, item_id) DO UPDATE SET rate=excluded.rate",
                (body.source_id, body.item_id, body.rate),
            )
    return _drop_rate_view(body.item_id, body.source_id)


@router.delete("/settings/drop-rates")
@router.delete("/drop-rates")
def delete_drop_rate(_: GMAccount, item_id: str, source_id: str | None = None):
    _validate_drop_item(item_id)
    with connection.transaction() as conn:
        if source_id is None:
            conn.execute("DELETE FROM global_drop_rates WHERE item_id = ?", (item_id,))
        else:
            conn.execute(
                "DELETE FROM source_drop_rates WHERE source_id = ? AND item_id = ?",
                (source_id, item_id),
            )
    return _drop_rate_view(item_id, source_id, allow_missing_source=True)


@router.put("/settings/hunt")
def set_hunt_settings(body: HuntSettingsRequest, _: GMAccount):
    with connection.transaction() as conn:
        conn.executemany(
            "INSERT INTO server_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [
                ("settle_floor_seconds", str(body.settle_floor_seconds)),
                ("huntable_win_rate", str(body.huntable_win_rate)),
            ],
        )
    return {
        "settle_floor_seconds": body.settle_floor_seconds,
        "huntable_win_rate": body.huntable_win_rate,
    }


@router.put("/settings/announcement")
def set_announcement(body: AnnouncementRequest, _: GMAccount):
    text = body.text.strip()
    now = datetime.now(timezone.utc).isoformat()
    with connection.transaction() as conn:
        if text:
            conn.executemany(
                "INSERT INTO server_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [("announcement", text), ("announcement_at", now)],
            )
        else:
            conn.execute(
                "DELETE FROM server_settings WHERE key IN ('announcement', 'announcement_at')"
            )
    return {"text": text, "updated_at": now if text else None}


@router.get("/settings")
def get_server_settings(_: GMAccount):
    keys = tuple(_SETTING_DEFAULTS)
    with connection.get_connection() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM server_settings WHERE key IN ({','.join('?' * len(keys))})",
            keys,
        ).fetchall()
    values = {row["key"]: float(row["value"]) for row in rows}
    return {key: values.get(key, default) for key, default in _SETTING_DEFAULTS.items()}


@router.get("/online-players")
def online_players(_: GMAccount):
    with connection.get_connection() as conn:
        rows = conn.execute("""
            SELECT a.id AS account_id, a.username, a.role, c.id AS character_id, c.name,
                   c.base_level, c.job_level, c.zeny
            FROM accounts a
            LEFT JOIN characters c ON c.account_id = a.id
            WHERE a.id IN (
                SELECT account_id FROM sessions WHERE expires_at > datetime('now')
            )
            ORDER BY a.id, c.id
        """).fetchall()
    return [dict(row) for row in rows]
