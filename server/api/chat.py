from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import characters as characters_repo
from server.repositories import chat as chat_repo
from server.repositories import guild as guild_repo

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=200)


def _character_name(account_id: int) -> str:
    rows = characters_repo.list_for_account(account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="沒有角色")
    return rows[0]["name"]


def _check_channel(account_id: int, channel: str) -> None:
    if channel == "world":
        return
    if channel.startswith("guild:"):
        try:
            guild_id = int(channel.split(":", 1)[1])
        except ValueError:
            raise HTTPException(status_code=400, detail="頻道格式錯誤")
        mine = guild_repo.mine(account_id)
        if mine is None or mine["id"] != guild_id:
            raise HTTPException(status_code=403, detail="你不在這個公會")
        return
    raise HTTPException(status_code=400, detail="未知頻道")


@router.post("")
def send_chat(body: ChatRequest, account_id: CurrentAccount):
    name = _character_name(account_id)
    _check_channel(account_id, body.channel)
    return chat_repo.post(body.channel, account_id, name, body.text)


@router.get("")
def read_chat(account_id: CurrentAccount, channel: str = "world", after: int = 0,
             recent: int = 0):
    if channel.startswith("guild:"):
        _check_channel(account_id, channel)
    if recent > 0:
        return chat_repo.recent(channel, min(recent, 100))
    return chat_repo.since(channel, after)
