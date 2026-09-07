from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import accounts as accounts_repo
from server.repositories import characters as characters_repo
from server.repositories import chat as chat_repo
from server.repositories import guild as guild_repo

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=200)


class WhisperRequest(BaseModel):
    to_name: str = Field(min_length=1, max_length=24)
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
    if channel.startswith("dm:"):
        ids = chat_repo.dm_ids(channel)
        if ids is None or len(ids) != 2 or channel != chat_repo.dm_channel(*ids):
            raise HTTPException(status_code=400, detail="頻道格式錯誤")
        if account_id not in ids:
            raise HTTPException(status_code=403, detail="不是你的私訊頻道")
        other = next(iter(ids - {account_id}))
        if accounts_repo.get_account(other) is None:
            raise HTTPException(status_code=404, detail="對方帳號不存在")
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
    if channel.startswith(("guild:", "dm:")):
        _check_channel(account_id, channel)
    if recent > 0:
        return chat_repo.recent(channel, min(recent, 100))
    return chat_repo.since(channel, after)


@router.post("/whisper")
def send_whisper(body: WhisperRequest, account_id: CurrentAccount):
    name = _character_name(account_id)
    target = characters_repo.get_character_by_name(body.to_name.strip())
    if target is None:
        raise HTTPException(status_code=404, detail="找不到這個角色")
    to_account = target["account_id"]
    if to_account == account_id:
        raise HTTPException(status_code=400, detail="不能密語給自己")
    channel = chat_repo.dm_channel(account_id, to_account)
    msg = chat_repo.post(channel, account_id, name, body.text)
    msg["other_name"] = target["name"]
    return msg


@router.get("/threads")
def list_threads(account_id: CurrentAccount):
    threads = chat_repo.dm_threads(account_id)
    names = characters_repo.names_for_accounts([t["other_account"] for t in threads])
    for t in threads:
        t["other_name"] = names.get(t["other_account"], "未知")
    return threads
