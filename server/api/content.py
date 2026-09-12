from fastapi import APIRouter, HTTPException

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server import npc_buff
from server.repositories import characters as characters_repo
from server.settlement.drops import effective_drop_rate, load_drop_rate_overrides

router = APIRouter(prefix="/api/content", tags=["content"])
_content = load_content()


def _current_character(account_id: int):
    return characters_repo.get_active_character(account_id)


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


def _monster_body(monster, overrides=None) -> dict:
    overrides = overrides or load_drop_rate_overrides()
    body = monster.model_dump(mode="json")
    body["drops"] = [
        {
            **drop.model_dump(),
            "rate": effective_drop_rate(monster.id, drop.item_id, drop.rate, overrides),
            "item_name": _item_name(drop.item_id),
        }
        for drop in monster.drops
    ]
    return body


@router.get("/catalog")
def catalog(account_id: CurrentAccount):
    """網頁前端一次抓齊靜態內容（地圖 / 怪 / 物品 / 裝備 / 卡 / 職業 / 技能）。"""
    overrides = load_drop_rate_overrides()
    def dump(coll):
        return {
            k: (_monster_body(v, overrides) if hasattr(v, "drops")
                else v.model_dump(mode="json"))
            for k, v in coll.items()
        }
    return {
        "maps": dump(_content.maps),
        "monsters": dump(_content.monsters),
        "mvps": dump(_content.mvps),
        "items": dump(_content.items),
        "equipment": dump(_content.equipment),
        "cards": dump(_content.cards),
        "jobs": dump(_content.jobs),
        "skills": dump(_content.skills),
        "recipes": dump(_content.recipes),
        "npc_buff": {
            "name": npc_buff.NAME, "stats": npc_buff.STATS,
            "one_time_cost": npc_buff.ONE_TIME_COST,
            "one_time_duration_s": npc_buff.ONE_TIME_DURATION_S,
            "hourly_cost": npc_buff.HOURLY_COST,
            "hourly_interval_s": npc_buff.HOURLY_INTERVAL_S,
        },
    }


@router.get("/monsters/{monster_id}")
def monster_detail(monster_id: str, account_id: CurrentAccount):
    monster = _content.monsters.get(monster_id) or _content.mvps.get(monster_id)
    if monster is None:
        raise HTTPException(status_code=404, detail="怪物不存在")
    return _monster_body(monster)


def _detail(kind: str, item_id: str, account_id: int):
    item = _get(kind, item_id)
    body = item.model_dump(mode="json")
    if kind == "equipment":
        char = _current_character(account_id)
        reasons = []
        if char:
            job = _content.jobs.get(char["job_id"])
            if item.job_ids and not (set(item.job_ids) & _content.job_ancestry(char["job_id"])):
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
