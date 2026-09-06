from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import accounts as accounts_repo
from server.repositories import trade as trade_repo

router = APIRouter(prefix="/api/trade", tags=["trade"])


class OfferRequest(BaseModel):
    to_username: str


class PutRequest(BaseModel):
    item_id: str | None = None
    qty: int = Field(default=1, ge=1)
    equipment_instance_id: int | None = None


@router.post("/offer")
def offer(body: OfferRequest, account_id: CurrentAccount):
    target = accounts_repo.get_account_by_username(body.to_username)
    if target is None:
        raise HTTPException(status_code=404, detail="找不到對方帳號")
    try:
        tid = trade_repo.offer(account_id, target["id"])
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"trade_id": tid}


@router.get("/pending")
def pending(account_id: CurrentAccount):
    return trade_repo.pending(account_id)


@router.get("/{trade_id}")
def table(trade_id: int, account_id: CurrentAccount):
    try:
        return trade_repo.table(trade_id)
    except trade_repo.TradeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


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
