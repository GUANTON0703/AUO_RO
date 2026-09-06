import json
import random
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth.dependencies import CurrentAccount
from server.config import get_settings
from server.content import load_content
from server.progression import CharacterSnapshot, build_player_combatant
from server.progression.levels import apply_base_exp, apply_job_exp
from server.repositories import characters as characters_repo
from server.settlement import HuntConfig, settle

router = APIRouter(prefix="/api/hunt", tags=["hunt"])

_content = load_content()

_STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartRequest(BaseModel):
    map_id: str
    monster_id: str | None = None


def _current_character(account_id: int):
    rows = characters_repo.list_for_account(account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="沒有角色")
    return rows[0]


def _snapshot(row, *, hp=None, sp=None) -> CharacterSnapshot:
    return CharacterSnapshot(
        name=row["name"], job_id=row["job_id"],
        base_level=row["base_level"], job_level=row["job_level"],
        stats={k: row[f"stat_{k}"] for k in _STAT_KEYS},
        learned_skills=json.loads(row["learned_skills"]),
        equipped=[],
        hp=hp, sp=sp,
    )


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
    if monster_id not in map_def.monster_ids:
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


def _settle_current(row) -> dict:
    if row["hunting_map_id"] is None:
        raise HTTPException(status_code=409, detail="目前沒有在掛機")

    settings = get_settings()
    snap = _snapshot(row, hp=row["hunt_hp"], sp=row["hunt_sp"])
    player = build_player_combatant(snap, _content)
    monster = _content.get_monster(row["hunting_monster_id"])
    job = _content.get_job(row["job_id"])

    now = datetime.now(timezone.utc)
    last = datetime.fromisoformat(row["hunt_last_settled_at"])
    elapsed = max(0.0, (now - last).total_seconds())
    offline = elapsed > settings.online_grace_seconds

    rng = random.Random(hash(row["hunt_last_settled_at"]) & 0xFFFFFFFF)
    result = settle(
        player, monster, elapsed, HuntConfig.from_settings(settings), rng,
        offline=offline, pity_in=json.loads(row["hunt_pity"]), potion_count=0,
    )

    new_bl, new_bexp, _ = apply_base_exp(row["base_level"], row["base_exp"], result.base_exp)
    new_jl, new_jexp, _ = apply_job_exp(row["job_level"], row["job_exp"],
                                        result.job_exp, job.tier)
    characters_repo.apply_progression(
        row["id"], base_level=new_bl, base_exp=new_bexp,
        job_level=new_jl, job_exp=new_jexp, zeny_delta=result.zeny,
    )
    characters_repo.merge_hunt_loot(row["id"], result.drops, result.pity_out)
    characters_repo.update_hunt_progress(
        row["id"], hp=result.final_hp, sp=result.final_sp,
        last_settled_at=now.isoformat(),
    )
    if result.retreated:
        characters_repo.clear_hunt_state(row["id"])

    fresh = characters_repo.get_character(row["id"])
    return {
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
