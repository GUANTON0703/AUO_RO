import json
import random
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth.dependencies import CurrentAccount
from server.config import get_settings
from server.content import load_content
from server.db import connection
from server.progression import CharacterSnapshot, EquippedPiece, build_player_combatant
from server.progression.levels import apply_base_exp, apply_job_exp
from server.repositories import characters as characters_repo
from server.repositories import inventory
from server.settlement import HuntConfig, settle
from server.settlement.huntable import huntable_monsters, pick_start_monster
from server.settlement.strategy import HuntStrategy

router = APIRouter(prefix="/api/hunt", tags=["hunt"])

_content = load_content()

_STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")
_strategies: dict[int, HuntStrategy] = {}
# character_id -> {"batch_id": iso 時間戳, "events": [...]}；記憶體暫存，重啟掉了無所謂
_last_batch: dict[int, dict] = {}
# character_id -> (快取鍵, 可打怪清單)；避免每次結算都重跑勝率模擬
_hunt_meta: dict[int, tuple] = {}


def _forget_hunt(cid: int) -> None:
    _last_batch.pop(cid, None)
    _hunt_meta.pop(cid, None)


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
    buy_potions: bool = False
    sell_items: bool = False


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
    strategy = _strategies.get(character_id, HuntStrategy())
    return HuntStrategyRequest.model_validate(asdict(strategy)).model_dump()


@router.put("/strategy/{character_id}")
def put_hunt_strategy(character_id: int, body: HuntStrategyRequest, account_id: CurrentAccount):
    _owned_character(character_id, account_id)
    _strategies[character_id] = HuntStrategy(**body.model_dump())
    _hunt_meta.pop(character_id, None)   # 策略改了，可打怪清單要重算
    return body.model_dump()


def _snapshot(row, *, hp=None, sp=None) -> CharacterSnapshot:
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
        hp=hp, sp=sp,
    )


def _pick_potion(character_id: int):
    """回傳 (item_id, heal, qty)；沒有可用補品回 (None, 0, 0)。"""
    inv = inventory.list_inventory(character_id)
    best = (None, 0, 0)
    for item_id, qty in inv["items"].items():
        item = _content.items.get(item_id)
        if item is None or item.kind != "consumable" or qty <= 0:
            continue
        heal = max(
            (e.get("amount", 0) for e in item.effects if e.get("type") == "heal_hp"),
            default=0,
        )
        if heal > best[1]:
            best = (item_id, heal, qty)
    return best


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

    strategy = _strategies.get(row["id"], HuntStrategy())
    if picked is not None:
        for mid in picked:
            if mid not in map_def.monster_ids:
                raise HTTPException(status_code=400, detail="該怪不在此地圖")
        strategy.include_monsters = picked
    _strategies[row["id"]] = strategy

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

    now = _now_iso()
    characters_repo.set_hunt_state(
        row["id"], map_id=body.map_id, monster_id=monster_id,
        started_at=now, last_settled_at=now,
        hp=player.max_hp, sp=player.max_sp,
    )
    _forget_hunt(row["id"])
    return {"map_id": body.map_id, "monster_id": monster_id,
            "hunt_hp": player.max_hp, "hunt_sp": player.max_sp}


def _character_block(row) -> dict:
    return {
        "base_level": row["base_level"], "base_exp": row["base_exp"],
        "job_level": row["job_level"], "job_exp": row["job_exp"],
        "job_id": row["job_id"], "zeny": row["zeny"],
        "hunt_hp": row["hunt_hp"], "hunt_sp": row["hunt_sp"],
    }


def _no_op_settlement(fresh) -> dict:
    """別的並發請求已結算過時回這個：目前角色狀態、無增量。"""
    batch = _last_batch.get(fresh["id"], {})
    return {
        "monster_id": fresh["hunting_monster_id"],
        "monster_name": _content.get_monster(fresh["hunting_monster_id"]).name,
        "batch_id": batch.get("batch_id"),
        "kills": fresh["hunt_kills"], "base_exp": fresh["hunt_base_exp"],
        "job_exp": fresh["hunt_job_exp"], "zeny": fresh["hunt_zeny"], "drops": {},
        "offline": False, "effective_seconds": fresh["hunt_seconds"],
        "retreated": False, "retreat_reason": None, "events": [],
        "character": _character_block(fresh),
    }


def _accumulated_snapshot(row) -> dict:
    """未達結算地板時回這個：目前場次累積值 + 最後一批事件，不重算、不寫入。"""
    batch = _last_batch.get(row["id"], {})
    return {
        "monster_id": row["hunting_monster_id"],
        "monster_name": _content.get_monster(row["hunting_monster_id"]).name,
        "batch_id": batch.get("batch_id"),
        "kills": row["hunt_kills"], "base_exp": row["hunt_base_exp"],
        "job_exp": row["hunt_job_exp"], "zeny": row["hunt_zeny"], "drops": {},
        "offline": False, "effective_seconds": row["hunt_seconds"],
        "retreated": False, "retreat_reason": None,
        "events": batch.get("events", []),
        "character": _character_block(row),
    }


def _settle_current(row, *, force=False) -> dict:
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

    # 結算防抖：距上次結算太近就只回累積值，不重算（省 CPU/寫入）。
    # 這個門檻很小（預設幾秒），不影響「感覺有在跑」。真正的防浪費靠下面的
    # 「只用掉湊完整場的時間、剩下留給下次」。
    if not force and not offline and elapsed < cfg.settle_floor_seconds:
        return _accumulated_snapshot(row)

    snap = _snapshot(row, hp=row["hunt_hp"], sp=row["hunt_sp"])
    player = build_player_combatant(snap, _content)
    monster = _content.get_monster(row["hunting_monster_id"])
    job = _content.get_job(row["job_id"])

    # 併發防護：BEGIN IMMEDIATE 序列化競爭的 status 請求。交易內重讀時間戳，
    # 若已被別的請求結算過就直接回目前狀態；否則立刻「認領」（寫回 now），
    # 讓同時進來的第二個請求走上面那條分支、不重複套用結算。
    with connection.transaction() as conn:
        current_last = conn.execute(
            "SELECT hunt_last_settled_at FROM characters WHERE id = ?", (row["id"],)
        ).fetchone()[0]
        if current_last != initial_last:
            return _no_op_settlement(characters_repo.get_character(row["id"]))
        conn.execute(
            "UPDATE characters SET hunt_last_settled_at = ? WHERE id = ?",
            (now.isoformat(), row["id"]),
        )

    potion_id, potion_heal, potion_count = _pick_potion(row["id"])

    rng = random.Random(hash(row["hunt_last_settled_at"]) & 0xFFFFFFFF)
    result = settle(
        player, monster, elapsed, cfg, rng,
        offline=offline, pity_in=json.loads(row["hunt_pity"]),
        potion_item_id=potion_id, potion_heal=potion_heal, potion_count=potion_count,
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
        return _accumulated_snapshot(characters_repo.get_character(row["id"]))

    new_bl, new_bexp, _ = apply_base_exp(row["base_level"], row["base_exp"], result.base_exp)
    new_jl, new_jexp, _ = apply_job_exp(row["job_level"], row["job_exp"],
                                        result.job_exp, job.tier)
    characters_repo.apply_progression(
        row["id"], base_level=new_bl, base_exp=new_bexp,
        job_level=new_jl, job_exp=new_jexp, zeny_delta=result.zeny,
    )
    characters_repo.merge_hunt_loot(row["id"], result.drops, result.pity_out)
    inventory.apply_drops(row["id"], result.drops)
    if potion_id and result.potions_used:
        inventory.consume_item(row["id"], potion_id, result.potions_used)

    # 線上結算只「用掉」湊完整場戰鬥的時間，剩下的留給下次 → 玩家一直輪詢
    # 也不會把零碎時間燒光。離線批次結算則整段吃掉。
    if force or offline:
        settled_until = now
        hunt_secs_delta = result.effective_seconds
    else:
        settled_until = min(now, last + timedelta(seconds=result.consumed_seconds))
        hunt_secs_delta = result.consumed_seconds

    characters_repo.update_hunt_progress(
        row["id"], hp=result.final_hp, sp=result.final_sp,
        last_settled_at=settled_until.isoformat(),
        kills=result.kills, base_exp=result.base_exp,
        job_exp=result.job_exp, zeny=result.zeny,
        seconds=hunt_secs_delta,
    )

    retreated = result.retreated
    retreat_reason = result.retreat_reason
    if retreated:
        characters_repo.clear_hunt_state(row["id"])
        _hunt_meta.pop(row["id"], None)
    else:
        after = characters_repo.get_character(row["id"])
        map_def = _content.maps[row["hunting_map_id"]]
        strategy = _strategies.get(row["id"], HuntStrategy())
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
    _last_batch[row["id"]] = {"batch_id": batch_id, "events": events}

    fresh = characters_repo.get_character(row["id"])
    # 輪替後目標可能已換，回傳新的（撤退清空後 fall back 到這次打的那隻）
    cur_mid = fresh["hunting_monster_id"] or row["hunting_monster_id"]
    return {
        "monster_id": cur_mid,
        "monster_name": _content.get_monster(cur_mid).name,
        "batch_id": batch_id,
        "kills": fresh["hunt_kills"],
        "base_exp": fresh["hunt_base_exp"],
        "job_exp": fresh["hunt_job_exp"],
        "zeny": fresh["hunt_zeny"],
        "drops": result.drops,
        "offline": offline,
        "effective_seconds": fresh["hunt_seconds"],
        "retreated": retreated,
        "retreat_reason": retreat_reason,
        "events": events,
        "character": _character_block(fresh),
    }


@router.get("/status")
def hunt_status(account_id: CurrentAccount):
    return _settle_current(_current_character(account_id))


@router.post("/stop")
def stop_hunt(account_id: CurrentAccount):
    row = _current_character(account_id)
    out = _settle_current(row, force=True)
    characters_repo.clear_hunt_state(row["id"])
    _forget_hunt(row["id"])
    return out
