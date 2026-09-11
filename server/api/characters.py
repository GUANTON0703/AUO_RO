import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.config import get_settings
from server.content import load_content
from server.progression import (
    CharacterSnapshot, EquippedPiece, build_player_combatant, maintained_buff_list,
)
from server.progression.skills import skill_points_available
from server.progression.stats import stat_points_available
from server.repositories import characters as characters_repo
from server.repositories import inventory
from shared.models import CharacterPublic

_STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CreateCharacterRequest(BaseModel):
    # 不允許 [ ] —— 客戶端用 rich markup 渲染名字，方括號會讓畫面解析失敗
    name: str = Field(min_length=1, max_length=24, pattern=r"^[^\[\]]+$")


def _to_public(row) -> CharacterPublic:
    return CharacterPublic(
        id=row["id"],
        name=row["name"],
        job_id=row["job_id"],
        base_level=row["base_level"],
        job_level=row["job_level"],
        base_exp=row["base_exp"],
        job_exp=row["job_exp"],
        stat_str=row["stat_str"],
        stat_agi=row["stat_agi"],
        stat_vit=row["stat_vit"],
        stat_int=row["stat_int"],
        stat_dex=row["stat_dex"],
        stat_luk=row["stat_luk"],
        stat_points=stat_points_available(
            row["base_level"], {k: row[f"stat_{k}"] for k in _STAT_KEYS},
            bool(row["is_rebirth"]),
        ),
        skill_points=skill_points_available(
            row["job_level"], json.loads(row["learned_skills"]),
            carried=row["skill_points"],
        ),
        is_rebirth=bool(row["is_rebirth"]),
        zeny=row["zeny"],
        location_map=row["location_map"],
        learned_skills=json.loads(row["learned_skills"]),
    )


@router.get("", response_model=list[CharacterPublic])
def list_characters(account_id: CurrentAccount):
    return [_to_public(r) for r in characters_repo.list_for_account(account_id)]


@router.post("", status_code=201, response_model=CharacterPublic)
def create_character(body: CreateCharacterRequest, account_id: CurrentAccount):
    settings = get_settings()
    try:
        row = characters_repo.create_within_limit(
            account_id,
            body.name,
            location_map=settings.starting_map,
            max_count=settings.max_characters_per_account,
        )
    except characters_repo.NameTakenError:
        raise HTTPException(status_code=409, detail="角色名稱已被使用")
    if row is None:
        raise HTTPException(
            status_code=409,
            detail=f"已達角色數上限（{settings.max_characters_per_account}）",
        )
    inventory.grant_starter_kit(row["id"])
    return _to_public(row)


@router.get("/{character_id}/sheet")
def character_sheet(character_id: int, account_id: CurrentAccount):
    row = characters_repo.get_character(character_id)
    if row is None or row["account_id"] != account_id:
        raise HTTPException(status_code=404, detail="找不到角色")
    content = load_content()
    skill_toggles = characters_repo.get_hunt_strategy(character_id).get("skill_toggles") or {}
    snap = CharacterSnapshot(
        name=row["name"],
        job_id=row["job_id"],
        base_level=row["base_level"],
        job_level=row["job_level"],
        stats={k: row[f"stat_{k}"] for k in _STAT_KEYS},
        learned_skills=json.loads(row["learned_skills"]),
        skill_toggles=skill_toggles,
        equipped=[
            EquippedPiece(
                equipment_id=e["equipment_id"],
                refine=e["refine"],
                card_ids=list(e["card_ids"]),
            )
            for e in inventory.list_equipped(character_id)
        ],
    )
    c = build_player_combatant(snap, content)
    return {
        "max_hp": c.max_hp,
        "max_sp": c.max_sp,
        "atk": c.atk,
        "matk": c.matk,
        "defense": c.defense,
        "mdef": c.mdef,
        "hit": c.hit,
        "flee": c.flee,
        "aspd": c.aspd,
        "crit": c.crit,
        "is_caster": c.is_caster,
        # 換裝後 max 可能變小，夾一下避免顯示超過上限（DB 值下次結算會自己修正）
        "hunt_hp": min(row["hunt_hp"], c.max_hp) if row["hunt_hp"] is not None else c.max_hp,
        "hunt_sp": min(row["hunt_sp"], c.max_sp) if row["hunt_sp"] is not None else c.max_sp,
        "maintained_buffs": maintained_buff_list(content, snap.learned_skills, skill_toggles),
    }


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, account_id: CurrentAccount):
    if not characters_repo.delete_character(character_id, account_id):
        raise HTTPException(status_code=404, detail="找不到角色")
