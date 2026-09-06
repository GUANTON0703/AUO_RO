from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import characters as characters_repo
from server.repositories import guild as guild_repo

router = APIRouter(prefix="/api/guild", tags=["guild"])


class CreateGuildRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)


def _character_name(account_id: int) -> str:
    rows = characters_repo.list_for_account(account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="沒有角色")
    return rows[0]["name"]


@router.post("")
def create_guild(body: CreateGuildRequest, account_id: CurrentAccount):
    try:
        return guild_repo.create(account_id, _character_name(account_id), body.name)
    except guild_repo.GuildNameTaken:
        raise HTTPException(status_code=409, detail="公會名稱已被使用")
    except guild_repo.GuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
def list_guilds(account_id: CurrentAccount):
    return guild_repo.list_all()


@router.get("/mine")
def my_guild(account_id: CurrentAccount):
    return guild_repo.mine(account_id)


@router.post("/leave")
def leave_guild(account_id: CurrentAccount):
    try:
        guild_repo.leave(account_id)
    except guild_repo.GuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/{guild_id}/join")
def join_guild(guild_id: int, account_id: CurrentAccount):
    try:
        guild_repo.join(account_id, _character_name(account_id), guild_id)
    except guild_repo.GuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}
