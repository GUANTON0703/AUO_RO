from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import characters as characters_repo
from server.repositories import trade as trade_repo

router = APIRouter(prefix="/api/trade", tags=["trade"])


class OfferRequest(BaseModel):
    to_username: str          # 其實填角色名（欄位名沿用舊版相容）


class PutRequest(BaseModel):
    item_id: str | None = None
    qty: int = Field(default=1, ge=1)
    equipment_instance_id: int | None = None


@router.post("/offer")
def offer(body: OfferRequest, account_id: CurrentAccount):
    target = characters_repo.get_character_by_name(body.to_username.strip())
    if target is None:
        raise HTTPException(status_code=404, detail="找不到這個角色")
    try:
        tid = trade_repo.offer(account_id, target["account_id"])
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"trade_id": tid}


@router.get("/pending")
def pending(account_id: CurrentAccount):
    rows = trade_repo.pending(account_id)
    names = characters_repo.names_for_accounts([r["from_account"] for r in rows])
    for r in rows:
        r["from_name"] = names.get(r["from_account"], "？")
    return rows


@router.get("/{trade_id}")
def table(trade_id: int, account_id: CurrentAccount):
    try:
        t = trade_repo.table(trade_id)
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    names = characters_repo.names_for_accounts([t["from_account"], t["to_account"]])
    t["from_name"] = names.get(t["from_account"], "？")
    t["to_name"] = names.get(t["to_account"], "？")
    return t


@router.post("/{trade_id}/put")
def put(trade_id: int, body: PutRequest, account_id: CurrentAccount):
    try:
        if body.equipment_instance_id is not None:
            trade_repo.put(trade_id, account_id, equipment_id=body.equipment_instance_id)
        elif body.item_id is not None:
            trade_repo.put(trade_id, account_id, item_id=body.item_id, qty=body.qty)
        else:
            raise HTTPException(status_code=400, detail="需指定 item_id 或 equipment_instance_id")
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return trade_repo.table(trade_id)


@router.post("/{trade_id}/confirm")
def confirm(trade_id: int, account_id: CurrentAccount):
    try:
        return trade_repo.confirm(trade_id, account_id)
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{trade_id}/cancel")
def cancel(trade_id: int, account_id: CurrentAccount):
    try:
        return trade_repo.cancel(trade_id, account_id)
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
