import json
import random
import threading
from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.config import get_settings
from server.content import load_content
from server.db import connection
from server.loot.pricing import item_sell_price
from server.progression import CharacterSnapshot, EquippedPiece, build_player_combatant
from server.progression.levels import apply_base_exp, apply_job_exp
from server.repositories import characters as characters_repo
from server.repositories import inventory
from server.settlement import HuntConfig, settle
from server.settlement.huntable import huntable_monsters, pick_start_monster
from server.settlement.profile import estimate_fight_profile
from server.settlement.strategy import HuntStrategy

router = APIRouter(prefix="/api/hunt", tags=["hunt"])

_content = load_content()

_STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")
# character_id -> {"batch_id": iso 時間戳, "events": [...]}；記憶體暫存，重啟掉了無所謂
_last_batch: dict[int, dict] = {}
# character_id -> (快取鍵, 可打怪清單)；避免每次結算都重跑勝率模擬
_hunt_meta: dict[int, tuple] = {}
# character_id -> 上次拿到暖啟動加成的時間；擋 start/stop 連點刷進度
_warm_start_at: dict[int, "datetime"] = {}
# 已標記、還沒被第一次 /status 消化的暖啟動
_warm_start_pending: set[int] = set()
_WARM_START_COOLDOWN = 90.0
_settlement_locks: dict[int, threading.Lock] = {}
_settlement_locks_guard = threading.Lock()
_COMBAT_EVENT_KINDS = {
    "attack", "skill", "heal", "kill", "fled", "status_applied", "status_expired",
}


def _forget_hunt(cid: int) -> None:
    _last_batch.pop(cid, None)
    _hunt_meta.pop(cid, None)


def _discard_settlement_lock(cid: int) -> None:
    with _settlement_locks_guard:
        _settlement_locks.pop(cid, None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartRequest(BaseModel):
    map_id: str
    monster_ids: list[str] | None = None
    monster_id: str | None = None   # 舊版單選相容


class HuntStrategyRequest(BaseModel):
    include_monsters: list[str] = []
    exclude_monsters: list[str] = []
    flee_on_boss: bool = True
    auto_potion: bool = True
    potion_item_id: str | None = None
    potion_hp_pct: float = Field(default=0.5, ge=0.05, le=0.95)
    auto_buy_potion: bool = False
    buy_potion_id: str | None = None
    buy_potion_upto: int = Field(default=0, ge=0, le=999)
    auto_sp_potion: bool = False
    sp_potion_item_id: str | None = None
    sp_potion_pct: float = Field(default=0.3, ge=0.05, le=0.95)
    auto_buy_sp_potion: bool = False
    buy_sp_potion_id: str | None = None
    buy_sp_potion_upto: int = Field(default=0, ge=0, le=999)
    sell_item_ids: list[str] = []
    skill_min_sp_pct: float = Field(default=0.0, ge=0.0, le=0.95)
    primary_skill_id: str | None = None
    skill_toggles: dict[str, bool] = {}
    auto_buff_potions: list[str] = []


def _load_strategy(character_id: int) -> HuntStrategy:
    data = characters_repo.get_hunt_strategy(character_id)
    known = {f.name for f in fields(HuntStrategy)}
    return HuntStrategy(**{k: v for k, v in data.items() if k in known})


def _current_character(account_id: int):
    rows = characters_repo.list_for_account(account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="沒有角色")
    return rows[0]


def _owned_character(character_id: int, account_id: int):
    row = next((r for r in characters_repo.list_for_account(account_id) if r["id"] == character_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return row


@router.get("/strategy/{character_id}")
def get_hunt_strategy(character_id: int, account_id: CurrentAccount):
    _owned_character(character_id, account_id)
    strategy = _load_strategy(character_id)
    return HuntStrategyRequest.model_validate(asdict(strategy)).model_dump()


@router.put("/strategy/{character_id}")
def put_hunt_strategy(character_id: int, body: HuntStrategyRequest, account_id: CurrentAccount):
    _owned_character(character_id, account_id)
    characters_repo.set_hunt_strategy(character_id, body.model_dump())
    _hunt_meta.pop(character_id, None)   # 策略改了，可打怪清單要重算
    return body.model_dump()


def _snapshot(row, *, hp=None, sp=None, apply_prefs=True, active_item_buffs=None) -> CharacterSnapshot:
    try:
        strat = json.loads(row["hunt_strategy"] or "{}") if apply_prefs else {}
    except (KeyError, IndexError, TypeError):
        strat = {}
    return CharacterSnapshot(
        name=row["name"], job_id=row["job_id"],
        base_level=row["base_level"], job_level=row["job_level"],
        stats={k: row[f"stat_{k}"] for k in _STAT_KEYS},
        learned_skills=json.loads(row["learned_skills"]),
        equipped=[
            EquippedPiece(
                equipment_id=e["equipment_id"], refine=e["refine"],
                card_ids=list(e["card_ids"]),
            )
            for e in inventory.list_equipped(row["id"])
        ],
        primary_skill_id=strat.get("primary_skill_id"),
        skill_toggles=strat.get("skill_toggles") or {},
        hp=hp, sp=sp,
        active_item_buffs=active_item_buffs or {},
    )


def _heal_amount(item) -> int:
    if item is None:
        return 0
    return max((e.get("amount", 0) for e in item.effects
               if e.get("type") == "heal_hp"), default=0)


def _sp_restore_amount(item) -> int:
    if item is None:
        return 0
    return max((e.get("amount", 0) for e in item.effects
               if e.get("type") == "heal_sp"), default=0)


def _usable(item, base_level: int) -> bool:
    return item is not None and item.kind == "consumable" \
        and base_level >= item.required_level


def _buff_effect(item) -> dict | None:
    if item is None:
        return None
    return next((e for e in item.effects if e.get("type") == "buff"), None)


def _refresh_active_buffs(character_id: int, strategy, base_level: int, now) -> dict:
    """讀目前還沒過期的 buff 藥，過期的清掉；設定裡有勾自動喝、目前沒生效、
    背包有貨的就喝一瓶續上。回傳 {item_id: {stat: 加成值}} 給combatant折進面板用
    （不含 expires_at 這種 metadata）。"""
    stored = characters_repo.get_active_potion_buffs(character_id)
    active: dict = {}
    for item_id, info in stored.items():
        try:
            expires_at = datetime.fromisoformat(info["expires_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > now:
            active[item_id] = info

    for item_id in strategy.auto_buff_potions:
        if item_id in active:
            continue
        item = _content.items.get(item_id)
        effect = _buff_effect(item)
        if not effect or not _usable(item, base_level):
            continue
        if inventory.item_qty(character_id, item_id) <= 0:
            continue
        inventory.consume_item(character_id, item_id, 1)
        expires_at = now + timedelta(seconds=effect.get("duration_s", 60))
        active[item_id] = {"expires_at": expires_at.isoformat(), "stats": effect.get("stats", {})}

    if active != stored:
        characters_repo.set_active_potion_buffs(character_id, active)
    return {item_id: info.get("stats", {}) for item_id, info in active.items()}


def _pick_potion(character_id: int, preferred_id: str | None = None,
                 base_level: int = 1):
    """回傳 (item_id, heal, qty)；沒有可用補品回 (None, 0, 0)。
    指定 preferred_id 且背包有、能回血、等級也夠 → 用它；否則自動挑回血最多的。
    等級不足的補品直接跳過（跟裝備一樣，買得到但用不了）。"""
    qty_of = inventory.item_qty(character_id, preferred_id) if preferred_id else 0
    if preferred_id and qty_of > 0 and _usable(_content.items.get(preferred_id), base_level):
        heal = _heal_amount(_content.items.get(preferred_id))
        if heal > 0:
            return (preferred_id, heal, qty_of)
    inv = inventory.list_inventory(character_id)
    best = (None, 0, 0)
    for item_id, qty in inv["items"].items():
        item = _content.items.get(item_id)
        if qty <= 0 or not _usable(item, base_level):
            continue
        heal = _heal_amount(item)
        if heal > best[1]:
            best = (item_id, heal, qty)
    return best


def _pick_sp_potion(character_id: int, preferred_id: str | None = None,
                    base_level: int = 1):
    """回傳 (item_id, restore, qty)；沒有可用 SP 藥水回 (None, 0, 0)。
    指定 preferred_id 且背包有、能回 SP、等級也夠 → 用它；否則自動挑回 SP 最多的。"""
    qty_of = inventory.item_qty(character_id, preferred_id) if preferred_id else 0
    if preferred_id and qty_of > 0 and _usable(_content.items.get(preferred_id), base_level):
        restore = _sp_restore_amount(_content.items.get(preferred_id))
        if restore > 0:
            return (preferred_id, restore, qty_of)
    inv = inventory.list_inventory(character_id)
    best = (None, 0, 0)
    for item_id, qty in inv["items"].items():
        item = _content.items.get(item_id)
        if qty <= 0 or not _usable(item, base_level):
            continue
        restore = _sp_restore_amount(item)
        if restore > best[1]:
            best = (item_id, restore, qty)
    return best


def _auto_buy_potions(character_id: int, strategy, base_level: int = 1) -> int:
    """掛機自動補水：買到手上有 buy_potion_upto 瓶，錢不夠就買能買的。回傳花了多少 Zeny。"""
    if not strategy.auto_buy_potion or strategy.buy_potion_upto <= 0:
        return 0
    pid = strategy.buy_potion_id or "red_potion"
    item = _content.items.get(pid)
    if item is None or not item.npc_buy or item.npc_buy <= 0:
        return 0
    if not _usable(item, base_level) or _heal_amount(item) <= 0:
        return 0
    have = inventory.item_qty(character_id, pid)
    want = strategy.buy_potion_upto - have
    if want <= 0:
        return 0
    current_zeny = characters_repo.get_character(character_id)["zeny"]
    buy_n = min(want, current_zeny // item.npc_buy)
    if buy_n <= 0:
        return 0
    cost = buy_n * item.npc_buy
    if characters_repo.spend_zeny(character_id, cost):
        inventory.add_item(character_id, pid, buy_n)
        return cost
    return 0


def _auto_buy_sp_potions(character_id: int, strategy, base_level: int = 1) -> int:
    """掛機自動補 SP 藥水：買到手上有 buy_sp_potion_upto 瓶，錢不夠就買能買的。回傳花了多少 Zeny。"""
    if not strategy.auto_buy_sp_potion or strategy.buy_sp_potion_upto <= 0:
        return 0
    pid = strategy.buy_sp_potion_id or "blue_potion"
    item = _content.items.get(pid)
    if item is None or not item.npc_buy or item.npc_buy <= 0:
        return 0
    if not _usable(item, base_level) or _sp_restore_amount(item) <= 0:
        return 0
    have = inventory.item_qty(character_id, pid)
    want = strategy.buy_sp_potion_upto - have
    if want <= 0:
        return 0
    current_zeny = characters_repo.get_character(character_id)["zeny"]
    buy_n = min(want, current_zeny // item.npc_buy)
    if buy_n <= 0:
        return 0
    cost = buy_n * item.npc_buy
    if characters_repo.spend_zeny(character_id, cost):
        inventory.add_item(character_id, pid, buy_n)
        return cost
    return 0


def _auto_sell(character_id: int, strategy) -> int:
    """每次結算把 sell_item_ids 裡的道具整批賣掉，回傳賣得的 Zeny。"""
    gained = 0
    sold: dict = {}
    for iid in strategy.sell_item_ids or []:
        item = _content.items.get(iid)
        if item is None:
            continue
        qty = inventory.item_qty(character_id, iid)
        if qty > 0 and inventory.consume_item(character_id, iid, qty):
            gained += item_sell_price(item) * qty
            sold[iid] = qty
    if gained:
        characters_repo.adjust_zeny(character_id, gained)
        characters_repo.reduce_hunt_loot(character_id, sold)
    return gained


@router.post("/start")
def start_hunt(body: StartRequest, account_id: CurrentAccount):
    row = _current_character(account_id)
    map_def = _content.maps.get(body.map_id)
    if map_def is None:
        raise HTTPException(status_code=400, detail="地圖不存在")
    if row["base_level"] < map_def.unlock_base_level:
        raise HTTPException(
            status_code=400,
            detail=f"Base Level 未達地圖解鎖需求（{map_def.unlock_base_level}）",
        )

    # monster_ids 有帶（含空 list = 明確要自動）→ 覆蓋指定怪；
    # 完全沒帶 → 沿用既有 strategy 的 include_monsters。
    if body.monster_ids is not None:
        picked = list(body.monster_ids)
    elif body.monster_id:
        picked = [body.monster_id]
    else:
        picked = None

    strategy = _load_strategy(row["id"])
    if picked is not None:
        for mid in picked:
            if mid not in map_def.monster_ids:
                raise HTTPException(status_code=400, detail="該怪不在此地圖")
        strategy.include_monsters = picked
    characters_repo.set_hunt_strategy(row["id"], asdict(strategy))

    player = build_player_combatant(_snapshot(row), _content)
    cfg = HuntConfig.from_settings(get_settings())
    monster_id = pick_start_monster(
        player, map_def, strategy, _content, random.Random(), cfg.huntable_win_rate
    )
    if monster_id is None:
        raise HTTPException(
            status_code=400,
            detail="這張地圖的怪你現在都打不贏，先加點或換更弱的地圖。",
        )

    now_dt = datetime.now(timezone.utc)
    # 暖啟動：標記這個角色，第一次 /status 直接送一場戰鬥的量，玩家按下掛機
    # 幾秒內就看到打鬥、不用乾等二十幾秒。連點 start/stop 有冷卻擋著。
    last_warm = _warm_start_at.get(row["id"])
    if last_warm is None or (now_dt - last_warm).total_seconds() > _WARM_START_COOLDOWN:
        _warm_start_pending.add(row["id"])
        _warm_start_at[row["id"]] = now_dt
    else:
        _warm_start_pending.discard(row["id"])
    now = now_dt.isoformat()
    characters_repo.set_hunt_state(
        row["id"], map_id=body.map_id, monster_id=monster_id,
        started_at=now, last_settled_at=now,
        hp=player.max_hp, sp=player.max_sp,
    )
    _forget_hunt(row["id"])
    return {"map_id": body.map_id, "monster_id": monster_id,
            "hunt_hp": player.max_hp, "hunt_sp": player.max_sp}


def _active_potion_buffs_view(row) -> list:
    """給前端顯示用：{item_id, name, remaining_s}，過期的不列。"""
    try:
        stored = json.loads(row["active_potion_buffs"] or "{}")
    except (TypeError, ValueError):
        return []
    now = datetime.now(timezone.utc)
    out = []
    for item_id, info in stored.items():
        try:
            expires_at = datetime.fromisoformat(info["expires_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining = (expires_at - now).total_seconds()
        if remaining <= 0:
            continue
        item = _content.items.get(item_id)
        out.append({"item_id": item_id, "name": item.name if item else item_id,
                   "remaining_s": round(remaining)})
    return out


def _character_block(row) -> dict:
    return {
        "base_level": row["base_level"], "base_exp": row["base_exp"],
        "job_level": row["job_level"], "job_exp": row["job_exp"],
        "job_id": row["job_id"], "zeny": row["zeny"],
        "hunt_hp": row["hunt_hp"], "hunt_sp": row["hunt_sp"],
        "hunt_potions_used": row["hunt_potions_used"],
        "hunt_sp_potions_used": row["hunt_sp_potions_used"],
        "hunt_potion_zeny_spent": row["hunt_potion_zeny_spent"],
        "active_potion_buffs": _active_potion_buffs_view(row),
    }


def _loot(row) -> dict:
    """本場累積撿到的道具 {item_id: qty}。"""
    try:
        return json.loads(row["hunt_loot"]) if row["hunt_loot"] else {}
    except (KeyError, TypeError, ValueError):
        return {}


def _event_view(batch: dict | None, requested_cursor: str | None,
                *, force_empty: bool = False) -> tuple[dict, list, str]:
    batch = batch or {}
    cursor = batch.get("cursor")
    events = list(batch.get("events", []))
    if force_empty or (requested_cursor is not None and requested_cursor == cursor):
        events = []
    mode = batch.get("mode", "live")
    return {
        "batch_id": batch.get("batch_id"),
        "cursor": cursor,
        "mode": mode,
        "events": events,
    }, events, mode


def _with_event_state(payload: dict, *, row, batch: dict | None,
                      requested_cursor: str | None, force_empty: bool = False) -> dict:
    event_batch, events, mode = _event_view(batch, requested_cursor, force_empty=force_empty)
    payload["events"] = events
    payload["event_cursor"] = event_batch["cursor"]
    payload["event_batch"] = event_batch
    if payload.get("retreated"):
        payload["hunt_state"] = "retreated"
        payload["combat_state"] = "idle"
    elif row["hunting_map_id"] is not None:
        payload["hunt_state"] = "active"
        payload["combat_state"] = (
            "combat" if mode == "live"
            and any(e.get("kind") in _COMBAT_EVENT_KINDS for e in events)
            else "hunting"
        )
    else:
        payload["hunt_state"] = "idle"
        payload["combat_state"] = "idle"
    return payload


def _no_op_settlement(fresh, event_cursor: str | None = None) -> dict:
    """別的並發請求已結算過時回這個：目前角色狀態、無增量。"""
    batch = _last_batch.get(fresh["id"], {})
    payload = {
        "monster_id": fresh["hunting_monster_id"],
        "monster_name": _content.get_monster(fresh["hunting_monster_id"]).name,
        "batch_id": batch.get("batch_id"),
        "pace_seconds": batch.get("pace_seconds", 0.0),
        "buffs": batch.get("buffs", []),
        "kills": fresh["hunt_kills"], "base_exp": fresh["hunt_base_exp"],
        "job_exp": fresh["hunt_job_exp"], "zeny": fresh["hunt_zeny"], "drops": {},
        "loot": _loot(fresh),
        "offline": False, "effective_seconds": fresh["hunt_seconds"],
        "retreated": False, "retreat_reason": None,
        "character": _character_block(fresh),
    }
    return _with_event_state(payload, row=fresh, batch=batch,
                             requested_cursor=event_cursor, force_empty=True)


def _probe_hunt_buffs(row) -> list:
    """掛機剛開始、還沒有結算批次時，跑一場拿 buff 狀態給畫面顯示。"""
    from server.settlement.engine import _probe_active_buffs
    try:
        player = build_player_combatant(
            _snapshot(row, hp=row["hunt_hp"], sp=row["hunt_sp"]), _content)
        monster = _content.get_monster(row["hunting_monster_id"])
        cfg = HuntConfig.from_settings(get_settings())
        strat = _load_strategy(row["id"])
        return _probe_active_buffs(player, monster, random.Random(),
                                   cfg, strat.skill_min_sp_pct)
    except Exception:
        return []


def _accumulated_snapshot(row, event_cursor: str | None = None) -> dict:
    """未達結算地板時回這個：目前場次累積值 + 最後一批事件，不重算、不寫入。
    沒有結算批次時不探測 combat；短輪詢只應讀狀態，不能偷偷跑一場模擬。"""
    batch = _last_batch.get(row["id"], {})
    buffs = batch.get("buffs", [])
    payload = {
        "monster_id": row["hunting_monster_id"],
        "monster_name": _content.get_monster(row["hunting_monster_id"]).name,
        "batch_id": batch.get("batch_id"),
        "pace_seconds": batch.get("pace_seconds", 0.0),
        "buffs": buffs,
        "kills": row["hunt_kills"], "base_exp": row["hunt_base_exp"],
        "job_exp": row["hunt_job_exp"], "zeny": row["hunt_zeny"], "drops": {},
        "loot": _loot(row),
        "offline": False, "effective_seconds": row["hunt_seconds"],
        "retreated": False, "retreat_reason": None,
        "character": _character_block(row),
    }
    return _with_event_state(payload, row=row, batch=batch,
                             requested_cursor=event_cursor)


def _settlement_lock(character_id: int) -> threading.Lock:
    with _settlement_locks_guard:
        return _settlement_locks.setdefault(character_id, threading.Lock())


def _settle_current(row, *, force=False, event_cursor: str | None = None) -> dict:
    """Serialize one character's full settlement, including the final progress write.

    The DB claim protects the normal path, but an online settlement deliberately writes
    back only the consumed seconds. A second request that starts after that write could
    otherwise mistake the remaining seconds for a new batch. The non-blocking lock makes
    that overlapping request an explicit no-op instead of applying rewards twice.
    """
    if row["hunting_map_id"] is None:
        raise HTTPException(status_code=409, detail="目前沒有在掛機")
    lock = _settlement_lock(row["id"])
    if force:
        lock.acquire()
        acquired = True
    else:
        acquired = lock.acquire(blocking=False)
    if not acquired:
        fresh = characters_repo.get_character(row["id"])
        if fresh["hunting_map_id"] is None:
            raise HTTPException(status_code=409, detail="目前沒有在掛機")
        return _no_op_settlement(fresh, event_cursor)
    try:
        return _settle_current_locked(row, force=force, event_cursor=event_cursor)
    finally:
        lock.release()
        if force:
            _discard_settlement_lock(row["id"])


def _settle_current_locked(row, *, force=False, event_cursor: str | None = None) -> dict:
    if row["hunting_map_id"] is None:
        raise HTTPException(status_code=409, detail="目前沒有在掛機")

    settings = get_settings()
    cfg = HuntConfig.from_settings(settings)

    now = datetime.now(timezone.utc)
    initial_last = row["hunt_last_settled_at"]
    last = datetime.fromisoformat(initial_last)
    if last.tzinfo is None:            # 舊資料或外部寫入的 naive 時間戳，當 UTC
        last = last.replace(tzinfo=timezone.utc)
    elapsed = max(0.0, (now - last).total_seconds())
    offline = elapsed > settings.online_grace_seconds
    warm_start = row["id"] in _warm_start_pending

    # 結算防抖：距上次結算太近就只回累積值，不重算（省 CPU/寫入）。
    # 暖啟動要跳過防抖，讓玩家按下掛機的第一次 /status 就結算得出東西。
    if not force and not offline and not warm_start \
            and elapsed < cfg.settle_floor_seconds:
        return _accumulated_snapshot(row, event_cursor)

    strategy = _load_strategy(row["id"])
    active_buffs = _refresh_active_buffs(row["id"], strategy, row["base_level"], now)
    snap = _snapshot(row, hp=row["hunt_hp"], sp=row["hunt_sp"], active_item_buffs=active_buffs)
    player = build_player_combatant(snap, _content)
    monster = _content.get_monster(row["hunting_monster_id"])
    job = _content.get_job(row["job_id"])

    # 暖啟動：消掉標記。只有在真實 elapsed 還很小（玩家剛按下掛機、還沒離開）時
    # 才把結算時間拉高到剛好一場戰鬥的量，讓第一次 /status 就打得出東西。
    # 真的離開一段時間才回來（elapsed 大）就照常結算，不要硬轉成線上。
    if warm_start and not force:
        _warm_start_pending.discard(row["id"])
        if elapsed < settings.online_grace_seconds:
            offline = False
            prof = estimate_fight_profile(player, monster, random.Random(), samples=6)
            one_fight = prof.avg_rounds * cfg.round_seconds + cfg.rest_seconds
            elapsed = max(elapsed, one_fight + cfg.round_seconds * 2)

    # 併發防護：BEGIN IMMEDIATE 序列化競爭的 status 請求。交易內重讀時間戳，
    # 若已被別的請求結算過就直接回目前狀態；否則立刻「認領」（寫回 now），
    # 讓同時進來的第二個請求走上面那條分支、不重複套用結算。
    with connection.transaction() as conn:
        current_last = conn.execute(
            "SELECT hunt_last_settled_at FROM characters WHERE id = ?", (row["id"],)
        ).fetchone()[0]
        if current_last != initial_last:
            return _no_op_settlement(characters_repo.get_character(row["id"]), event_cursor)
        conn.execute(
            "UPDATE characters SET hunt_last_settled_at = ? WHERE id = ?",
            (now.isoformat(), row["id"]),
        )

    potion_zeny_spent = _auto_buy_potions(row["id"], strategy, row["base_level"])
    potion_zeny_spent += _auto_buy_sp_potions(row["id"], strategy, row["base_level"])
    # 買水這筆花費馬上入帳，不管這次有沒有湊出一場戰鬥可結算（下面有提早回傳的分支）
    if potion_zeny_spent:
        characters_repo.add_hunt_potion_zeny_spent(row["id"], potion_zeny_spent)

    if strategy.auto_potion:
        potion_id, potion_heal, potion_count = _pick_potion(
            row["id"], strategy.potion_item_id, row["base_level"])
    else:
        potion_id, potion_heal, potion_count = (None, 0, 0)

    if strategy.auto_sp_potion:
        sp_potion_id, sp_potion_restore, sp_potion_count = _pick_sp_potion(
            row["id"], strategy.sp_potion_item_id, row["base_level"])
    else:
        sp_potion_id, sp_potion_restore, sp_potion_count = (None, 0, 0)

    # HP / SP 藥水是同一道具（例：蜂王乳）→ 拆分數量，模擬時不會重複算同一批。
    # 取捨：這種設定下每個用途只拿一半，不追求最優配置（罕見設定，重寫成共享池
    # 不值得動戰鬥引擎）。偏向 SP（無條件進位），qty=1 時 SP 至少有 1 瓶。
    if potion_id and potion_id == sp_potion_id:
        sp_share = (potion_count + 1) // 2
        potion_count, sp_potion_count = potion_count - sp_share, sp_share

    # 喝水加成藥：補品回復量放大；活力藥水：場間自然回血回魔速度放大
    if player.potion_heal_pct:
        potion_heal = round(potion_heal * (1 + player.potion_heal_pct / 100))
        sp_potion_restore = round(sp_potion_restore * (1 + player.potion_heal_pct / 100))
    if player.regen_bonus_pct:
        cfg = replace(cfg, hp_regen_frac_per_sec=cfg.hp_regen_frac_per_sec
                      * (1 + player.regen_bonus_pct / 100))

    rng = random.Random(hash(row["hunt_last_settled_at"]) & 0xFFFFFFFF)
    result = settle(
        player, monster, elapsed, cfg, rng,
        offline=offline, pity_in=json.loads(row["hunt_pity"]),
        potion_item_id=potion_id, potion_heal=potion_heal, potion_count=potion_count,
        hp_threshold=strategy.potion_hp_pct,
        skill_min_sp_pct=strategy.skill_min_sp_pct,
        sp_potion_item_id=sp_potion_id, sp_potion_restore=sp_potion_restore,
        sp_potion_count=sp_potion_count, sp_potion_frac=strategy.sp_potion_pct,
    )

    # 這次沒湊出任何一場戰鬥（時間還在攢）→ 撤銷剛才的「認領」，什麼都不寫，
    # 直接回累積值。下次時間夠了再結算。這樣一直輪詢也不會燒掉零碎時間。
    if not offline and not result.retreated and result.kills == 0 \
            and result.consumed_seconds <= 0:
        with connection.get_connection() as conn:
            conn.execute(
                "UPDATE characters SET hunt_last_settled_at = ? WHERE id = ?",
                (initial_last, row["id"]),
            )
        return _accumulated_snapshot(characters_repo.get_character(row["id"]), event_cursor)

    new_bl, new_bexp, _ = apply_base_exp(row["base_level"], row["base_exp"], result.base_exp)
    new_jl, new_jexp, _ = apply_job_exp(row["job_level"], row["job_exp"],
                                        result.job_exp, job.tier)
    characters_repo.apply_progression(
        row["id"], base_level=new_bl, base_exp=new_bexp,
        job_level=new_jl, job_exp=new_jexp, zeny_delta=result.zeny,
    )
    characters_repo.merge_hunt_loot(row["id"], result.drops, result.pity_out)
    inventory.apply_drops(row["id"], result.drops)
    # HP / SP 藥水若是同一個道具（例：蜂王乳），合併扣一次
    _spent: dict[str, int] = {}
    if potion_id and result.potions_used:
        _spent[potion_id] = _spent.get(potion_id, 0) + result.potions_used
    if sp_potion_id and result.sp_potions_used:
        _spent[sp_potion_id] = _spent.get(sp_potion_id, 0) + result.sp_potions_used
    for _pid, _n in _spent.items():
        inventory.consume_item(row["id"], _pid, _n)
    sell_gain = _auto_sell(row["id"], strategy)

    # 線上結算只「用掉」湊完整場戰鬥的時間，剩下的留給下次 → 玩家一直輪詢
    # 也不會把零碎時間燒光。離線批次結算則整段吃掉。
    if force or offline:
        settled_until = now
        hunt_secs_delta = result.effective_seconds
    else:
        settled_until = min(now, last + timedelta(seconds=result.consumed_seconds))
        hunt_secs_delta = result.consumed_seconds

    # 狂暴藥：持續掉血，類似中毒，跟這批結算代表的秒數成正比（每 10 秒扣一次）
    berserk = active_buffs.get("berserk_potion")
    final_hp = result.final_hp
    if berserk:
        drain_item = _content.items.get("berserk_potion")
        drain_effect = _buff_effect(drain_item) or {}
        drain_pct = drain_effect.get("drain_pct_per_tick", 0)
        ticks = max(0.0, result.consumed_seconds if not offline else result.effective_seconds) / 10
        drain = round(player.max_hp * drain_pct / 100 * ticks)
        final_hp = max(1, final_hp - drain)

    characters_repo.update_hunt_progress(
        row["id"], hp=final_hp, sp=result.final_sp,
        last_settled_at=settled_until.isoformat(),
        kills=result.kills, base_exp=result.base_exp,
        job_exp=result.job_exp, zeny=result.zeny + sell_gain,
        seconds=hunt_secs_delta,
        potions_used=result.potions_used, sp_potions_used=result.sp_potions_used,
    )

    retreated = result.retreated
    retreat_reason = result.retreat_reason
    if retreated:
        characters_repo.clear_hunt_state(row["id"])
        _hunt_meta.pop(row["id"], None)
    else:
        after = characters_repo.get_character(row["id"])
        map_def = _content.maps[row["hunting_map_id"]]
        pick_player = build_player_combatant(
            _snapshot(after, hp=after["hunt_hp"], sp=after["hunt_sp"]), _content
        )
        # 快取鍵涵蓋所有影響「能不能打」的東西：戰鬥數值（含裝備/加點/技能
        # 的結果）、勝率門檻、指定/排除清單。任何一項變了就重跑模擬。
        meta_key = (
            round(pick_player.atk), round(pick_player.matk), round(pick_player.max_hp),
            round(pick_player.max_sp), round(pick_player.hit), round(pick_player.flee),
            round(pick_player.defense), round(pick_player.mdef), round(pick_player.crit),
            pick_player.aspd, after["learned_skills"],
            cfg.huntable_win_rate,
            tuple(sorted(strategy.include_monsters)),
            tuple(sorted(strategy.exclude_monsters)),
        )
        cached = _hunt_meta.get(row["id"])
        if cached and cached[0] == meta_key:
            candidates = cached[1]
        else:
            candidates = huntable_monsters(
                pick_player, map_def, strategy, _content, random.Random(),
                cfg.huntable_win_rate,
            )
            _hunt_meta[row["id"]] = (meta_key, candidates)
        if not candidates:
            characters_repo.clear_hunt_state(row["id"])
            _hunt_meta.pop(row["id"], None)
            retreated = True
            retreat_reason = "此地圖的怪你目前都打不贏"
        else:
            cur = row["hunting_monster_id"]
            if cur not in candidates:
                characters_repo.update_hunt_target(row["id"], candidates[0])
            elif result.kills > 0 and len(candidates) > 1:
                # 打完一批才輪替，換隻怪打；只是在攢時間就不動目標
                idx = candidates.index(cur)
                characters_repo.update_hunt_target(
                    row["id"], candidates[(idx + 1) % len(candidates)]
                )

    batch_id = now.isoformat()
    events = [asdict(e) for e in result.events]
    # 這批事件代表的遊戲內時間：客戶端用它把逐擊訊息平均攤開，填滿到下一批之間
    pace_seconds = max(result.consumed_seconds, result.effective_seconds if offline else 0.0)
    _last_batch[row["id"]] = {"batch_id": batch_id, "cursor": batch_id,
                              "mode": "offline" if offline else "live",
                              "events": events, "pace_seconds": pace_seconds,
                              "buffs": result.active_buffs}

    fresh = characters_repo.get_character(row["id"])
    # 輪替後目標可能已換，回傳新的（撤退清空後 fall back 到這次打的那隻）
    cur_mid = fresh["hunting_monster_id"] or row["hunting_monster_id"]
    payload = {
        "monster_id": cur_mid,
        "monster_name": _content.get_monster(cur_mid).name,
        "batch_id": batch_id,
        "pace_seconds": pace_seconds,
        "buffs": result.active_buffs,
        "kills": fresh["hunt_kills"],
        "base_exp": fresh["hunt_base_exp"],
        "job_exp": fresh["hunt_job_exp"],
        "zeny": fresh["hunt_zeny"],
        "drops": result.drops,
        "loot": _loot(fresh),
        "sold": sell_gain,
        "offline": offline,
        "effective_seconds": fresh["hunt_seconds"],
        "retreated": retreated,
        "retreat_reason": retreat_reason,
        "character": _character_block(fresh),
    }
    return _with_event_state(payload, row=fresh, batch=_last_batch[row["id"]],
                             requested_cursor=event_cursor)


@router.get("/status")
def hunt_status(account_id: CurrentAccount, cursor: str | None = None,
                event_cursor: str | None = None):
    return _settle_current(
        _current_character(account_id),
        event_cursor=event_cursor or cursor,
    )


@router.post("/stop")
def stop_hunt(account_id: CurrentAccount):
    row = _current_character(account_id)
    _warm_start_pending.discard(row["id"])   # 沒消化到的暖啟動作廢，不留到下次
    out = _settle_current(row, force=True)
    characters_repo.clear_hunt_state(row["id"])
    _forget_hunt(row["id"])
    return out
