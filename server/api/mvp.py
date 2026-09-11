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

from server.api.hunt import (
    _current_character, _load_strategy, _pick_potion, _pick_sp_potion, _snapshot,
)

router = APIRouter(prefix="/api/mvp", tags=["mvp"])

_content = load_content()

_REGION_ZH = {
    "prontera": "普隆德拉", "morroc": "摩洛克", "payon": "拜楊",
    "geffen": "蓋菲恩", "aldebaran": "阿爾迪巴朗", "nifflheim": "尼芙海姆",
}

# 所有 MVP 統一冷卻 20 分鐘（蓋過 mvps.json 各自的 cooldown_hours）
_MVP_COOLDOWN_HOURS = 20 / 60


class ChallengeRequest(BaseModel):
    mvp_id: str
    flee_hp_frac: float | None = None


@router.get("")
def list_mvp(account_id: CurrentAccount):
    row = _current_character(account_id)
    out = []
    def _drop_name(item_id: str) -> str:
        for pool in (_content.items, _content.equipment, _content.cards):
            if item_id in pool:
                return pool[item_id].name
        return item_id

    for m in _content.mvps.values():
        home = _content.maps.get(m.home_map_id)
        town = getattr(home, "town", None) if home else None
        gs = mvp_repo.global_status(m.id)
        out.append({
            "id": m.id,
            "name": m.name,
            "level": m.level,
            "home_map_id": m.home_map_id,
            "home_map_name": home.name if home else m.home_map_id,
            "region": town or "other",
            "region_name": _REGION_ZH.get(town, "其他"),
            "available": gs is None,
            "seconds_remaining": gs["seconds_remaining"] if gs else 0,
            "last_killer": gs["killer"] if gs else None,
            "killed_ago": gs["killed_ago"] if gs else None,
            "cooldown_minutes": round(_MVP_COOLDOWN_HOURS * 60),
            "drops": [
                {"item_id": d.item_id, "name": _drop_name(d.item_id),
                 "rate": d.rate}
                for d in m.drops
            ],
        })
    return out


@router.post("/challenge")
def challenge(body: ChallengeRequest, account_id: CurrentAccount):
    row = _current_character(account_id)
    mvp = _content.mvps.get(body.mvp_id)
    if mvp is None:
        raise HTTPException(status_code=404, detail="MVP 不存在")
    gs = mvp_repo.global_status(mvp.id)
    if gs is not None:
        mins = round(gs["seconds_remaining"] / 60)
        raise HTTPException(
            status_code=400,
            detail=f"冷卻中（{mins} 分後復活，上次由 {gs['killer']} 擊殺）")

    job = _content.get_job(row["job_id"])
    active_buffs = characters_repo.active_buff_stats(row["id"])
    player = build_player_combatant(
        _snapshot(row, apply_prefs=False, active_item_buffs=active_buffs), _content)

    cfg = ChallengeConfig()
    if body.flee_hp_frac is not None:
        cfg.flee_hp_frac = max(0.0, min(0.9, body.flee_hp_frac))

    # 挑戰時也能照掛機的自動補品設定喝水
    strat = _load_strategy(row["id"])
    lv = row["base_level"]
    hp_id, hp_heal, hp_cnt = (
        _pick_potion(row["id"], strat.potion_item_id, lv)
        if strat.auto_potion else (None, 0, 0))
    sp_id, sp_restore, sp_cnt = (
        _pick_sp_potion(row["id"], strat.sp_potion_item_id, lv)
        if strat.auto_sp_potion else (None, 0, 0))
    if hp_id and hp_id == sp_id:
        share = (hp_cnt + 1) // 2
        hp_cnt, sp_cnt = hp_cnt - share, share

    rng = random.Random()
    result = challenge_mvp(
        player, mvp, cfg, rng, player_base_level=lv,
        potions=hp_cnt, potion_heal=hp_heal, potion_hp_frac=strat.potion_hp_pct,
        sp_potions=sp_cnt, sp_potion_restore=sp_restore,
        sp_potion_frac=strat.sp_potion_pct,
    )
    if result.potions_used and hp_id:
        inventory.consume_item(row["id"], hp_id, result.potions_used)
    if result.sp_potions_used and sp_id:
        inventory.consume_item(row["id"], sp_id, result.sp_potions_used)

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

    # 只有擊殺才進全服冷卻；打輸 / 撤退不鎖，其他人（或自己）還能再挑戰
    if result.outcome == "win":
        mvp_repo.set_global_kill(mvp.id, row["name"], _MVP_COOLDOWN_HOURS)

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
