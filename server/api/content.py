from fastapi import APIRouter, HTTPException

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.repositories import characters as characters_repo

router = APIRouter(prefix="/api/content", tags=["content"])
_content = load_content()


def _current_character(account_id: int):
    rows = characters_repo.list_for_account(account_id)
    return rows[0] if rows else None


def _item_name(item_id: str) -> str:
    for collection in (_content.items, _content.equipment, _content.cards):
        if item := collection.get(item_id):
            return item.name
    return item_id


def _get(kind: str, item_id: str):
    collection = getattr(_content, kind)
    item = collection.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="資料不存在")
    return item


@router.get("/monsters/{monster_id}")
def monster_detail(monster_id: str, account_id: CurrentAccount):
    monster = _content.monsters.get(monster_id) or _content.mvps.get(monster_id)
    if monster is None:
        raise HTTPException(status_code=404, detail="怪物不存在")
    body = monster.model_dump(mode="json")
    body["drops"] = [
        {**drop.model_dump(), "item_name": _item_name(drop.item_id)} for drop in monster.drops
    ]
    return body


def _detail(kind: str, item_id: str, account_id: int):
    item = _get(kind, item_id)
    body = item.model_dump(mode="json")
    if kind == "equipment":
        char = _current_character(account_id)
        reasons = []
        if char:
            job = _content.jobs.get(char["job_id"])
            if item.job_ids and char["job_id"] not in item.job_ids:
                reasons.append("職業不符")
            if char["base_level"] < item.required_level:
                reasons.append(f"Base Level 不足（需要 {item.required_level}）")
            body["requirements"] = {"met": not reasons, "reasons": reasons,
                                     "required_level": item.required_level,
                                     "job_ids": item.job_ids,
                                     "character_level": char["base_level"],
                                     "character_job_id": char["job_id"],
                                     "character_job_name": job.name if job else char["job_id"]}
        else:
            body["requirements"] = {"met": False, "reasons": ["沒有角色"]}
    return body


@router.get("/items/{item_id}")
def item_detail(item_id: str, account_id: CurrentAccount):
    return _detail("items", item_id, account_id)


@router.get("/cards/{item_id}")
def card_detail(item_id: str, account_id: CurrentAccount):
    return _detail("cards", item_id, account_id)


@router.get("/equipment/{item_id}")
def equipment_detail(item_id: str, account_id: CurrentAccount):
    return _detail("equipment", item_id, account_id)
