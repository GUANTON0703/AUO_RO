import copy
import random
from dataclasses import dataclass, field

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from server.settlement.config import HuntConfig
from server.settlement.drops import roll_drops
from server.settlement.economy import zeny_per_kill
from server.settlement.events import (
    KillBatchEvent, PotionUsedEvent, RareDropEvent, RetreatEvent,
)
from server.settlement.profile import estimate_fight_profile
from shared.content import MonsterDef


@dataclass
class SettlementResult:
    kills: int
    base_exp: int
    job_exp: int
    zeny: int
    drops: dict = field(default_factory=dict)
    potions_used: int = 0
    retreated: bool = False
    retreat_reason: str = ""
    real_elapsed_seconds: float = 0.0
    effective_seconds: float = 0.0
    pity_out: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    final_hp: int = 0
    final_sp: int = 0


def _rare_drop_events(monster: MonsterDef, drops: dict, cfg: HuntConfig) -> list:
    out: list = []
    for item_id, qty in drops.items():
        entry = next((d for d in monster.drops if d.item_id == item_id), None)
        if entry and entry.rate < cfg.rare_drop_cutoff:
            out.append(RareDropEvent(item_id, item_id, qty))
    return out


def settle(player: Combatant, monster: MonsterDef, elapsed_seconds: float,
           cfg: HuntConfig, rng: random.Random, *, offline: bool, pity_in: dict,
           potion_item_id: str | None = None, potion_heal: int = 0,
           potion_count: int = 0) -> SettlementResult:

    if offline:
        capped = min(elapsed_seconds, cfg.offline_cap_hours * 3600)
        effective = capped * cfg.offline_efficiency
    else:
        effective = float(elapsed_seconds)

    prof = estimate_fight_profile(player, monster, rng, samples=20)
    time_per_kill = prof.avg_rounds * cfg.round_seconds + cfg.rest_seconds
    potential = int(effective / time_per_kill) if time_per_kill > 0 else 0

    if prof.win_rate <= 0.0:
        return SettlementResult(
            kills=0, base_exp=0, job_exp=0, zeny=0, drops={}, potions_used=0,
            retreated=True, retreat_reason="打不過這裡的怪",
            real_elapsed_seconds=float(elapsed_seconds), effective_seconds=0.0,
            pity_out=dict(pity_in), events=[RetreatEvent("打不過這裡的怪", 0.0)],
            final_hp=player.hp, final_sp=player.sp,
        )

    if not offline and potential <= cfg.literal_sim_kill_cap:
        return _settle_literal(player, monster, elapsed_seconds, effective,
                               time_per_kill, cfg, rng, pity_in,
                               potion_item_id, potion_heal, potion_count)

    return _settle_statistical(player, monster, elapsed_seconds, effective,
                               time_per_kill, potential, prof, cfg, rng, offline,
                               pity_in, potion_item_id, potion_heal, potion_count)


def _settle_statistical(player, monster, elapsed_seconds, effective, time_per_kill,
                        potential, prof, cfg, rng, offline, pity_in,
                        potion_item_id, potion_heal, potion_count) -> SettlementResult:
    potions_used = 0
    retreated = False
    reason = ""

    need_potion_per_fight = 0.0
    if prof.avg_damage_taken > 0 and potion_heal > 0:
        need_potion_per_fight = prof.avg_damage_taken / potion_heal

    max_kills = potential
    if prof.avg_damage_taken > 0:
        if potion_heal <= 0 or potion_count <= 0:
            sustainable = int(player.max_hp / max(1.0, prof.avg_damage_taken))
            if sustainable < potential:
                max_kills = sustainable
                retreated, reason = True, "沒有補品，血量見底"
        else:
            affordable = int(potion_count / need_potion_per_fight)
            if affordable < potential:
                max_kills = affordable
                retreated, reason = True, "補品用盡"

    kills = round(prof.win_rate * max_kills)
    if need_potion_per_fight > 0:
        potions_used = min(potion_count, round(kills * need_potion_per_fight))
    used_seconds = kills * time_per_kill

    base_exp = kills * monster.base_exp
    job_exp = kills * monster.job_exp
    zeny = kills * zeny_per_kill(monster)
    drops, pity_out = roll_drops(monster.drops, kills, rng, offline=offline,
                                 pity_in=pity_in, cfg=cfg)

    events: list = []
    if kills > 0:
        events.append(KillBatchEvent(monster.name, kills, base_exp, job_exp, zeny))
    events += _rare_drop_events(monster, drops, cfg)
    if potions_used:
        events.append(PotionUsedEvent(potion_item_id or "", potion_item_id or "",
                                      potions_used, max(0, potion_count - potions_used)))
    if retreated:
        events.append(RetreatEvent(reason, used_seconds))

    return SettlementResult(
        kills=kills, base_exp=base_exp, job_exp=job_exp, zeny=zeny, drops=drops,
        potions_used=potions_used, retreated=retreated, retreat_reason=reason,
        real_elapsed_seconds=float(elapsed_seconds),
        effective_seconds=used_seconds if retreated else effective,
        pity_out=pity_out, events=events,
        final_hp=player.hp, final_sp=player.sp,
    )


def _settle_literal(player, monster, elapsed_seconds, effective, time_per_kill,
                    cfg, rng, pity_in, potion_item_id, potion_heal,
                    potion_count) -> SettlementResult:
    p = copy.deepcopy(player)
    p.hp, p.sp = p.max_hp, p.max_sp
    for s in p.skills:
        s._cd_left = 0

    potions_left = potion_count
    potions_used = 0
    kills = 0
    retreated = False
    reason = ""
    elapsed = 0.0
    threshold_hp = p.max_hp * cfg.potion_hp_threshold

    while elapsed + time_per_kill <= effective + 1e-9:
        # 場間補血：血量低於門檻且有補品才補，補到門檻以上或用完
        if p.hp < threshold_hp and potion_heal > 0:
            while potions_left > 0 and p.hp < threshold_hp:
                p.heal(potion_heal)
                potions_left -= 1
                potions_used += 1
        if p.hp < threshold_hp and potions_left <= 0 and potion_heal > 0:
            retreated, reason = True, "補品用盡，血量見底"
            break

        foe = Combatant.from_monster(monster)
        p.statuses = [s for s in p.statuses if s.kind != "dot"]
        for s in p.skills:
            s._cd_left = 0
        r = simulate_fight(p, foe, rng)
        elapsed += time_per_kill
        if r.winner == p.name:
            kills += 1
        else:
            retreated, reason = True, "戰鬥中被擊倒"
            break

        # 場間 SP 回復
        p.sp = min(p.max_sp, p.sp + round(cfg.sp_regen_per_sec * time_per_kill))

    base_exp = kills * monster.base_exp
    job_exp = kills * monster.job_exp
    zeny = kills * zeny_per_kill(monster)
    drops, pity_out = roll_drops(monster.drops, kills, rng, offline=False,
                                 pity_in=pity_in, cfg=cfg)

    events: list = []
    if kills > 0:
        events.append(KillBatchEvent(monster.name, kills, base_exp, job_exp, zeny))
    events += _rare_drop_events(monster, drops, cfg)
    if potions_used:
        events.append(PotionUsedEvent(potion_item_id or "", potion_item_id or "",
                                      potions_used, max(0, potions_left)))
    if retreated:
        events.append(RetreatEvent(reason, elapsed))

    return SettlementResult(
        kills=kills, base_exp=base_exp, job_exp=job_exp, zeny=zeny, drops=drops,
        potions_used=potions_used, retreated=retreated, retreat_reason=reason,
        real_elapsed_seconds=float(elapsed_seconds),
        effective_seconds=elapsed if retreated else effective,
        pity_out=pity_out, events=events,
        final_hp=p.hp, final_sp=p.sp,
    )
