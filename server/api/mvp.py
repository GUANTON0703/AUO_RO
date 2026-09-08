import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.mvp.challenge import ChallengeConfig, challenge_mvp
from server.progression import build_player_combatant
from server.progression.levels import apply_base_exp, apply_job_exp
from server.repositories import characters as characters_repo
from server.repositories import inventory
from server.repositories import mvp as mvp_repo

from server.api.hunt import _current_character, _snapshot

router = APIRouter(prefix="/api/mvp", tags=["mvp"])

_content = load_content()

# 所有 MVP 統一冷卻 20 分鐘（蓋過 mvps.json 各自的 cooldown_hours）
_MVP_COOLDOWN_HOURS = 20 / 60


class ChallengeRequest(BaseModel):
    mvp_id: str
    flee_hp_frac: float | None = None


@router.get("")
def list_mvp(account_id: CurrentAccount):
    row = _current_character(account_id)
    out = []
    for m in _content.mvps.values():
        home = _content.maps.get(m.home_map_id)
        out.append({
            "id": m.id,
            "name": m.name,
            "level": m.level,
            "home_map_id": m.home_map_id,
            "home_map_name": home.name if home else m.home_map_id,
            "available": mvp_repo.is_available(row["id"], m.id),
            "seconds_remaining": mvp_repo.seconds_remaining(row["id"], m.id),
            "cooldown_minutes": round(_MVP_COOLDOWN_HOURS * 60),
        })
    return out


@router.post("/challenge")
def challenge(body: ChallengeRequest, account_id: CurrentAccount):
    row = _current_character(account_id)
    mvp = _content.mvps.get(body.mvp_id)
    if mvp is None:
        raise HTTPException(status_code=404, detail="MVP 不存在")
    if not mvp_repo.is_available(row["id"], mvp.id):
        raise HTTPException(status_code=400, detail="冷卻中")

    job = _content.get_job(row["job_id"])
    player = build_player_combatant(_snapshot(row, apply_prefs=False), _content)

    cfg = ChallengeConfig()
    if body.flee_hp_frac is not None:
        cfg.flee_hp_frac = max(0.0, min(0.9, body.flee_hp_frac))

    rng = random.Random()
    result = challenge_mvp(player, mvp, cfg, rng, player_base_level=row["base_level"])

    if result.outcome == "win":
        inventory.apply_drops(row["id"], result.drops)
        new_bl, new_bexp, _ = apply_base_exp(row["base_level"], row["base_exp"], result.base_exp)
        new_jl, new_jexp, _ = apply_job_exp(row["job_level"], row["job_exp"],
                                            result.job_exp, job.tier)
        characters_repo.apply_progression(
            row["id"], base_level=new_bl, base_exp=new_bexp,
            job_level=new_jl, job_exp=new_jexp, zeny_delta=result.zeny,
        )
    elif result.outcome == "loss":
        new_bexp = max(0, row["base_exp"] - result.exp_penalty)
        characters_repo.apply_progression(
            row["id"], base_level=row["base_level"], base_exp=new_bexp,
            job_level=row["job_level"], job_exp=row["job_exp"], zeny_delta=0,
        )

    mvp_repo.set_cooldown(row["id"], mvp.id, _MVP_COOLDOWN_HOURS)

    fresh = characters_repo.get_character(row["id"])
    return {
        "outcome": result.outcome,
        "rounds": result.rounds,
        "base_exp": result.base_exp,
        "job_exp": result.job_exp,
        "zeny": result.zeny,
        "exp_penalty": result.exp_penalty,
        "drops": result.drops,
        "events": result.events,
        "character": {
            "base_level": fresh["base_level"], "base_exp": fresh["base_exp"],
            "job_level": fresh["job_level"], "job_exp": fresh["job_exp"],
            "job_id": fresh["job_id"], "zeny": fresh["zeny"],
        },
    }
