from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.repositories import characters as characters_repo
from server.repositories import storage as storage_repo

router = APIRouter(prefix="/api/storage", tags=["storage"])


def _current_character(account_id: int):
    row = characters_repo.get_active_character(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="沒有角色")
    return row


class MoveRequest(BaseModel):
    item_id: str | None = None
    qty: int = Field(default=1, ge=1)
    equipment_instance_id: int | None = None


@router.get("")
def get_storage(account_id: CurrentAccount):
    return storage_repo.list_storage(account_id)


@router.post("/deposit")
def deposit(body: MoveRequest, account_id: CurrentAccount):
    char = _current_character(account_id)
    try:
        if body.equipment_instance_id is not None:
            storage_repo.deposit_equipment(account_id, char["id"], body.equipment_instance_id)
        elif body.item_id is not None:
            storage_repo.deposit_item(account_id, char["id"], body.item_id, body.qty)
        else:
            raise HTTPException(status_code=400, detail="需指定 item_id 或 equipment_instance_id")
    except storage_repo.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return storage_repo.list_storage(account_id)


@router.post("/withdraw")
def withdraw(body: MoveRequest, account_id: CurrentAccount):
    char = _current_character(account_id)
    try:
        if body.equipment_instance_id is not None:
            storage_repo.withdraw_equipment(account_id, char["id"], body.equipment_instance_id)
        elif body.item_id is not None:
            storage_repo.withdraw_item(account_id, char["id"], body.item_id, body.qty)
        else:
            raise HTTPException(status_code=400, detail="需指定 item_id 或 equipment_instance_id")
    except storage_repo.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return storage_repo.list_storage(account_id)
