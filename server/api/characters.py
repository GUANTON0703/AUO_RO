from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.config import get_settings
from server.repositories import characters as characters_repo
from shared.models import CharacterPublic

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CreateCharacterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)


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
        stat_points=row["stat_points"],
        skill_points=row["skill_points"],
        zeny=row["zeny"],
        location_map=row["location_map"],
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
    return _to_public(row)


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, account_id: CurrentAccount):
    if not characters_repo.delete_character(character_id, account_id):
        raise HTTPException(status_code=404, detail="找不到角色")
