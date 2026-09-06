import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.progression.skills import can_learn, skill_points_available
from server.progression.stats import STAT_KEYS, STAT_MAX, stat_points_available
from server.repositories import characters as characters_repo

router = APIRouter(prefix="/api/characters", tags=["progression"])

_content = load_content()


def _owned(character_id: int, account_id: int):
    row = characters_repo.get_character(character_id)
    if row is None or row["account_id"] != account_id:
        raise HTTPException(status_code=404, detail="找不到角色")
    return row


def _stats_of(row) -> dict:
    return {k: row[f"stat_{k}"] for k in STAT_KEYS}


def _public(row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "job_id": row["job_id"],
        "base_level": row["base_level"], "job_level": row["job_level"],
        "base_exp": row["base_exp"], "job_exp": row["job_exp"],
        "zeny": row["zeny"],
        **{f"stat_{k}": row[f"stat_{k}"] for k in STAT_KEYS},
        "learned_skills": json.loads(row["learned_skills"]),
    }


class SkillRequest(BaseModel):
    skill_id: str
    level: int = Field(ge=1)


class JobChangeRequest(BaseModel):
    target_job_id: str


@router.post("/{character_id}/stats")
def allocate_stats(character_id: int, body: dict[str, int], account_id: CurrentAccount):
    row = _owned(character_id, account_id)
    if not body or any(k not in STAT_KEYS for k in body):
        raise HTTPException(status_code=400, detail="屬性名稱無效")
    if any(v < 0 for v in body.values()):
        raise HTTPException(status_code=400, detail="加點數不可為負")

    target = _stats_of(row)
    for k, delta in body.items():
        target[k] += delta
        if target[k] > STAT_MAX:
            raise HTTPException(status_code=400, detail=f"{k} 超過上限 {STAT_MAX}")

    if stat_points_available(row["base_level"], target) < 0:
        raise HTTPException(status_code=400, detail="屬性點不足")

    characters_repo.set_stats(character_id, target)
    return _public(_owned(character_id, account_id))


@router.post("/{character_id}/skills")
def learn_skill(character_id: int, body: SkillRequest, account_id: CurrentAccount):
    row = _owned(character_id, account_id)
    learned = json.loads(row["learned_skills"])
    available = skill_points_available(row["job_level"], learned, carried=0)
    ok, reason = can_learn(_content, row["job_id"], body.skill_id, body.level,
                           learned, available)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    learned[body.skill_id] = body.level
    characters_repo.set_learned_skills(character_id, learned)
    return _public(_owned(character_id, account_id))


@router.post("/{character_id}/jobchange")
def change_job(character_id: int, body: JobChangeRequest, account_id: CurrentAccount):
    row = _owned(character_id, account_id)
    target = _content.jobs.get(body.target_job_id)
    if target is None:
        raise HTTPException(status_code=400, detail="目標職業不存在")
    if target.parent_id != row["job_id"]:
        raise HTTPException(status_code=400, detail="無法從目前職業轉入此職")
    if row["job_level"] < target.change_job_level:
        raise HTTPException(
            status_code=400,
            detail=f"Job Level 未達門檻（需 {target.change_job_level}）",
        )
    characters_repo.set_job(character_id, body.target_job_id, 1, 0)
    return _public(_owned(character_id, account_id))
