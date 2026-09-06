import json
import random
from dataclasses import asdict
from datetime import datetime, timezone

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
from server.settlement.strategy import HuntStrategy

router = APIRouter(prefix="/api/hunt", tags=["hunt"])

_content = load_content()

_STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")
_strategies: dict[int, HuntStrategy] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartRequest(BaseModel):
    map_id: str
    monster_id: str | None = None


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


def _pick_monster(map_def, base_level: int) -> str:
    return min(
        map_def.monster_ids,
        key=lambda mid: abs(_content.get_monster(mid).level - base_level),
    )


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
    monster_id = body.monster_id or _pick_monster(map_def, row["base_level"])
    strategy = _strategies.get(row["id"], HuntStrategy())
    if monster_id not in map_def.monster_ids or not strategy.allows(monster_id):
        raise HTTPException(status_code=400, detail="該怪不在此地圖")

    player = build_player_combatant(_snapshot(row), _content)
    now = _now_iso()
    characters_repo.set_hunt_state(
        row["id"], map_id=body.map_id, monster_id=monster_id,
        started_at=now, last_settled_at=now,
        hp=player.max_hp, sp=player.max_sp,
    )
    return {"map_id": body.map_id, "monster_id": monster_id,
            "hunt_hp": player.max_hp, "hunt_sp": player.max_sp}


def _no_op_settlement(fresh) -> dict:
    """別的並發請求已結算過時回這個：目前角色狀態、無增量。"""
    return {
        "monster_id": fresh["hunting_monster_id"],
        "monster_name": _content.get_monster(fresh["hunting_monster_id"]).name,
        "kills": 0, "base_exp": 0, "job_exp": 0, "zeny": 0, "drops": {},
        "offline": False, "effective_seconds": 0.0,
        "retreated": False, "retreat_reason": None, "events": [],
        "character": {
            "base_level": fresh["base_level"], "base_exp": fresh["base_exp"],
            "job_level": fresh["job_level"], "job_exp": fresh["job_exp"],
            "job_id": fresh["job_id"], "zeny": fresh["zeny"],
            "hunt_hp": fresh["hunt_hp"], "hunt_sp": fresh["hunt_sp"],
        },
    }


def _settle_current(row) -> dict:
    if row["hunting_map_id"] is None:
        raise HTTPException(status_code=409, detail="目前沒有在掛機")

    settings = get_settings()
    snap = _snapshot(row, hp=row["hunt_hp"], sp=row["hunt_sp"])
    player = build_player_combatant(snap, _content)
    monster = _content.get_monster(row["hunting_monster_id"])
    job = _content.get_job(row["job_id"])

    now = datetime.now(timezone.utc)
    initial_last = row["hunt_last_settled_at"]

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

    last = datetime.fromisoformat(initial_last)
    if last.tzinfo is None:            # 舊資料或外部寫入的 naive 時間戳，當 UTC
        last = last.replace(tzinfo=timezone.utc)
    elapsed = max(0.0, (now - last).total_seconds())
    offline = elapsed > settings.online_grace_seconds

    potion_id, potion_heal, potion_count = _pick_potion(row["id"])

    rng = random.Random(hash(row["hunt_last_settled_at"]) & 0xFFFFFFFF)
    result = settle(
        player, monster, elapsed, HuntConfig.from_settings(settings), rng,
        offline=offline, pity_in=json.loads(row["hunt_pity"]),
        potion_item_id=potion_id, potion_heal=potion_heal, potion_count=potion_count,
    )

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
    characters_repo.update_hunt_progress(
        row["id"], hp=result.final_hp, sp=result.final_sp,
        last_settled_at=now.isoformat(),
    )
    if result.retreated:
        characters_repo.clear_hunt_state(row["id"])

    fresh = characters_repo.get_character(row["id"])
    return {
        "monster_id": row["hunting_monster_id"],
        "monster_name": monster.name,
        "kills": result.kills,
        "base_exp": result.base_exp,
        "job_exp": result.job_exp,
        "zeny": result.zeny,
        "drops": result.drops,
        "offline": offline,
        "effective_seconds": result.effective_seconds,
        "retreated": result.retreated,
        "retreat_reason": result.retreat_reason,
        "events": [asdict(e) for e in result.events],
        "character": {
            "base_level": fresh["base_level"], "base_exp": fresh["base_exp"],
            "job_level": fresh["job_level"], "job_exp": fresh["job_exp"],
            "job_id": fresh["job_id"], "zeny": fresh["zeny"],
            "hunt_hp": fresh["hunt_hp"], "hunt_sp": fresh["hunt_sp"],
        },
    }


@router.get("/status")
def hunt_status(account_id: CurrentAccount):
    return _settle_current(_current_character(account_id))


@router.post("/stop")
def stop_hunt(account_id: CurrentAccount):
    row = _current_character(account_id)
    out = _settle_current(row)
    characters_repo.clear_hunt_state(row["id"])
    return out
