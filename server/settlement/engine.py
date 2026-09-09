import copy
import math
import random
from dataclasses import dataclass, field, replace

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from server.settlement.config import HuntConfig
from server.settlement.drops import roll_drops
from server.settlement.economy import zeny_per_kill
from server.settlement.events import (
    KillBatchEvent, PotionUsedEvent, RareDropEvent, RetreatEvent,
)
from server.settlement.strategy import choose_hunt_event
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
    sp_potions_used: int = 0
    retreated: bool = False
    retreat_reason: str = ""
    real_elapsed_seconds: float = 0.0
    effective_seconds: float = 0.0
    # 這次結算實際「用掉」的線上秒數（湊完整場戰鬥的部分）。剩下的留給下次，
    # 避免玩家一直輪詢時零碎時間被丟掉。離線批次結算則等於全部時間。
    consumed_seconds: float = 0.0
    pity_out: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    final_hp: int = 0
    final_sp: int = 0
    # 結算結束時身上還在的 buff/debuff（給掛機畫面的人物框顯示）
    active_buffs: list = field(default_factory=list)


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
           potion_count: int = 0, hp_threshold: float | None = None,
           skill_min_sp_pct: float = 0.0,
           sp_potion_item_id: str | None = None, sp_potion_restore: int = 0,
           sp_potion_count: int = 0, sp_potion_frac: float = 0.0) -> SettlementResult:
    if hp_threshold is not None:
        cfg = replace(cfg, potion_hp_threshold=hp_threshold)

    random_event = choose_hunt_event(monster.role == "boss", rng, cfg)
    if random_event and random_event.kind == "boss_retreat":
        return SettlementResult(
            kills=0, base_exp=0, job_exp=0, zeny=0, retreated=True,
            retreat_reason="遇到 Boss，使用蒼蠅翼飛走",
            real_elapsed_seconds=float(elapsed_seconds), events=[random_event],
            pity_out=dict(pity_in), final_hp=player.hp, final_sp=player.sp,
        )

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
        result = _settle_literal(player, monster, elapsed_seconds, effective,
                               time_per_kill, cfg, rng, pity_in,
                               potion_item_id, potion_heal, potion_count,
                               skill_min_sp_pct,
                               sp_potion_item_id, sp_potion_restore,
                               sp_potion_count, sp_potion_frac)
    else:
        # 統計路徑（離線 / 超過逐場模擬上限）不逐場模擬，SP 藥水在這裡不生效：
        # result.sp_potions_used 恆為 0，SP 消耗只做粗估。自動買的 SP 藥水會留在
        # 背包，下次線上逐場結算才會用到，不會憑空消失。
        result = _settle_statistical(player, monster, elapsed_seconds, effective,
                               time_per_kill, potential, prof, cfg, rng, offline,
                               pity_in, potion_item_id, potion_heal, potion_count,
                               skill_min_sp_pct)
    if random_event:
        result.events.insert(0, random_event)
    return result


def _buffs_from_statuses(statuses, cfg) -> list:
    return [
        {"stat": s.stat, "magnitude": s.magnitude, "source": s.source,
         "remaining_s": round(s.duration * cfg.round_seconds)}
        for s in statuses if s.kind == "stat_mod" and s.magnitude > 0
    ]


def _probe_active_buffs(player, monster, rng, cfg, skill_min_sp_pct: float = 0.0) -> list:
    """統計路徑沒有逐場模擬，跑一場拿身上的 buff 狀態給畫面顯示用。"""
    probe = copy.deepcopy(player)
    for s in probe.skills:
        s._cd_left = 0
    simulate_fight(probe, Combatant.from_monster(monster), rng,
                   a_skill_min_sp_frac=skill_min_sp_pct)
    return _buffs_from_statuses(probe.statuses, cfg)


def _settle_statistical(player, monster, elapsed_seconds, effective, time_per_kill,
                        potential, prof, cfg, rng, offline, pity_in,
                        potion_item_id, potion_heal, potion_count,
                        skill_min_sp_pct=0.0) -> SettlementResult:
    potions_used = 0
    retreated = False
    reason = ""

    max_kills = potential

    # 1) 勝率 < 1 → 早晚會輸一場（= 陣亡）。幾何分布：平均 win_rate/(1-win_rate) 場後陣亡。
    if prof.win_rate < 1.0:
        expected_before_death = int(prof.win_rate / (1.0 - prof.win_rate))
        if expected_before_death < max_kills:
            max_kills = expected_before_death
            retreated, reason = True, "戰鬥中被擊倒"

    # 2) 每場淨損 = 平均受傷 - 場間自然回血。淨損 <= 0 → 靠回血無限撐。
    regen_per_fight = player.max_hp * cfg.hp_regen_frac_per_sec * time_per_kill
    net_dmg = prof.avg_damage_taken - regen_per_fight
    if net_dmg > 0:
        threshold_hp = player.max_hp * cfg.potion_hp_threshold
        buffer_hp = max(0.0, player.hp - threshold_hp)
        if potion_heal > 0 and potion_count > 0:
            sustainable = int((buffer_hp + potion_count * potion_heal) / net_dmg)
            if sustainable < max_kills:
                max_kills = sustainable
                retreated, reason = True, "補品用盡"
        else:
            sustainable = int(player.hp / net_dmg)
            if sustainable < max_kills:
                max_kills = sustainable
                retreated, reason = True, "沒有補品，血量見底"

    kills = max(0, max_kills)
    if potion_heal > 0 and net_dmg > 0:
        threshold_hp = player.max_hp * cfg.potion_hp_threshold
        buffer_hp = max(0.0, player.hp - threshold_hp)
        healing_needed = max(0.0, kills * net_dmg - buffer_hp)
        potions_used = min(potion_count, math.ceil(healing_needed / potion_heal))
    used_seconds = kills * time_per_kill

    base_exp = round(kills * monster.base_exp * cfg.experience_multiplier)
    job_exp = round(kills * monster.job_exp * cfg.experience_multiplier)
    # 偷竊：以每場成功機率估算額外 Zeny（統計路徑沒逐場模擬）。偷竊掛在普攻上，
    # 施法職多半不普攻 → 只算物理職，且再打折當作沒每場都摸到。
    steal_pct = min(100, getattr(player, "procs", {}).get("steal_loot", 0))
    steal_zeny = 0 if player.is_caster else round(
        kills * steal_pct / 100 * 0.6 * zeny_per_kill(monster) * 0.5
        * cfg.zeny_multiplier)
    zeny = round(kills * zeny_per_kill(monster) * cfg.zeny_multiplier) + steal_zeny
    drops, pity_out = roll_drops(monster.drops, kills, rng, offline=offline,
                                 pity_in=pity_in, cfg=cfg, source_id=monster.id)

    events: list = []
    if kills > 0:
        events.append(KillBatchEvent(monster.name, kills, base_exp, job_exp, zeny))
    events += _rare_drop_events(monster, drops, cfg)
    if potions_used:
        events.append(PotionUsedEvent(potion_item_id or "", potion_item_id or "",
                                      potions_used, max(0, potion_count - potions_used)))
    if retreated:
        events.append(RetreatEvent(reason, used_seconds))

    # kills==0（時間窗還不夠殺一隻）也要回 buff，不然掛機畫面會閃掉
    active_buffs = ([] if retreated
                    else _probe_active_buffs(player, monster, rng, cfg, skill_min_sp_pct))

    return SettlementResult(
        kills=kills, base_exp=base_exp, job_exp=job_exp, zeny=zeny, drops=drops,
        potions_used=potions_used, retreated=retreated, retreat_reason=reason,
        real_elapsed_seconds=float(elapsed_seconds),
        effective_seconds=used_seconds if retreated else effective,
        # 線上結算只用掉「湊完整場」的時間；離線走 now，這個值不會被用到
        consumed_seconds=used_seconds,
        pity_out=pity_out, events=events,
        final_hp=player.hp, final_sp=player.sp,
        active_buffs=active_buffs,
    )


def _settle_literal(player, monster, elapsed_seconds, effective, time_per_kill,
                    cfg, rng, pity_in, potion_item_id, potion_heal,
                    potion_count, skill_min_sp_pct=0.0,
                    sp_potion_item_id=None, sp_potion_restore=0,
                    sp_potion_count=0, sp_potion_frac=0.0) -> SettlementResult:
    # 從玩家目前的掛機狀態續算（不重置滿血），這樣連續掛機才會累積掉血
    p = copy.deepcopy(player)
    for s in p.skills:
        s._cd_left = 0

    potions_left = potion_count
    potions_used = 0
    sp_potions_left = sp_potion_count
    sp_potions_used = 0
    kills = 0
    steal_hits = 0
    combat_events: list = []
    retreated = False
    reason = ""
    elapsed = 0.0
    threshold_hp = p.max_hp * cfg.potion_hp_threshold
    threshold_sp = p.max_sp * sp_potion_frac

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

        # 場間補 SP：SP 低於門檻且有 SP 藥水才補。SP 見底不致命，不撤退。
        if p.sp < threshold_sp and sp_potion_restore > 0:
            while sp_potions_left > 0 and p.sp < threshold_sp:
                p.restore_sp(sp_potion_restore)
                sp_potions_left -= 1
                sp_potions_used += 1

        foe = Combatant.from_monster(monster)
        p.statuses = [s for s in p.statuses if s.kind != "dot"]
        for s in p.skills:
            s._cd_left = 0
        # 補品也能在戰鬥中喝：血量掉到門檻以下就補，撐過那些一場就會被打死的怪
        r = simulate_fight(p, foe, rng, a_potions=potions_left,
                           a_potion_heal=potion_heal,
                           a_potion_hp_frac=cfg.potion_hp_threshold,
                           a_skill_min_sp_frac=skill_min_sp_pct,
                           a_sp_potions=sp_potions_left,
                           a_sp_potion_restore=sp_potion_restore,
                           a_sp_potion_frac=sp_potion_frac)
        combat_events.extend(r.events)
        potions_left -= r.potions_used
        potions_used += r.potions_used
        sp_potions_left -= r.sp_potions_used
        sp_potions_used += r.sp_potions_used
        elapsed += time_per_kill
        if r.winner == p.name:
            kills += 1
            if r.stole:
                steal_hits += 1
        elif r.potions_used > 0 and potions_left <= 0:
            retreated, reason = True, "補品用盡，血量見底"
            break
        else:
            retreated, reason = True, "戰鬥中被擊倒"
            break

        # 場間 SP / HP 自然回復
        p.sp = min(p.max_sp, p.sp + round(cfg.sp_regen_per_sec * time_per_kill))
        p.heal(round(p.max_hp * cfg.hp_regen_frac_per_sec * time_per_kill))

    base_exp = round(kills * monster.base_exp * cfg.experience_multiplier)
    job_exp = round(kills * monster.job_exp * cfg.experience_multiplier)
    # 偷竊：成功的場次額外撈半隻怪的 Zeny
    steal_zeny = round(steal_hits * zeny_per_kill(monster) * 0.5 * cfg.zeny_multiplier)
    zeny = round(kills * zeny_per_kill(monster) * cfg.zeny_multiplier) + steal_zeny
    drops, pity_out = roll_drops(monster.drops, kills, rng, offline=False,
                                 pity_in=pity_in, cfg=cfg, source_id=monster.id)

    events: list = list(combat_events[-60:])
    if kills > 0:
        events.append(KillBatchEvent(monster.name, kills, base_exp, job_exp, zeny))
    events += _rare_drop_events(monster, drops, cfg)
    if potions_used:
        events.append(PotionUsedEvent(potion_item_id or "", potion_item_id or "",
                                      potions_used, max(0, potions_left)))
    if sp_potions_used:
        events.append(PotionUsedEvent(sp_potion_item_id or "", sp_potion_item_id or "",
                                      sp_potions_used, max(0, sp_potions_left)))
    if retreated:
        events.append(RetreatEvent(reason, elapsed))

    if retreated:
        active_buffs = []
    elif kills > 0:
        active_buffs = _buffs_from_statuses(p.statuses, cfg)
    else:
        # 時間窗還不夠殺一隻 → 探測一場拿 buff 狀態，別讓畫面閃掉
        active_buffs = _probe_active_buffs(player, monster, rng, cfg, skill_min_sp_pct)

    return SettlementResult(
        kills=kills, base_exp=base_exp, job_exp=job_exp, zeny=zeny, drops=drops,
        potions_used=potions_used, sp_potions_used=sp_potions_used,
        retreated=retreated, retreat_reason=reason,
        real_elapsed_seconds=float(elapsed_seconds),
        effective_seconds=elapsed,
        consumed_seconds=elapsed,
        pity_out=pity_out, events=events,
        final_hp=p.hp, final_sp=p.sp,
        active_buffs=active_buffs,
    )
