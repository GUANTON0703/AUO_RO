import random
from dataclasses import dataclass, field

from server.combat import elements
from server.combat.events import AttackEvent, FledEvent, HealEvent, KillEvent
from server.combat.formulas import (
    CRIT_MULTIPLIER, attacks_this_round, crit_chance, hit_chance, physical_damage,
)
from server.combat.skills import cast_skill
from server.combat.status import tick_statuses

MAX_ROUNDS_DEFAULT = 500


@dataclass
class FightResult:
    winner: str | None
    loser: str | None
    outcome: str            # "win" / "stalemate" / "fled"
    rounds: int
    winner_hp: int
    loser_hp: int
    events: list = field(default_factory=list)
    potions_used: int = 0   # 戰鬥中喝掉的補品數（只有玩家 a 會喝）
    stole: bool = False      # 這場有偷竊成功


def _buff_already_up(c, skill) -> bool:
    """技能的所有增益 stat 都還在身上 → 不用重放。"""
    for eff in skill.effects:
        if eff.get("type") != "buff":
            continue
        for stat in eff.get("stats", {}):
            if not any(st.kind == "stat_mod" and st.stat == stat for st in c.statuses):
                return False
    return True


def _pick_skill(c, min_sp_frac: float = 0.0):
    if min_sp_frac > 0 and c.sp < c.max_sp * min_sp_frac:
        return None            # 留魔力：SP 沒到門檻就不放主動技能，改普攻
    buffs, others = [], []
    for s in c.skills:
        if s.kind != "active" or s._cd_left > 0 or c.sp < s.sp_cost:
            continue
        if not _trigger_ok(c, s.trigger):
            continue
        if any(e.get("type") == "buff" for e in s.effects):
            if not _buff_already_up(c, s):     # 已經開著的 buff 不重放，改去攻擊
                buffs.append(s)
        else:
            others.append(s)
    # 先把缺的 buff 補上，補齊後才輪到攻擊 / 補血技能
    pool = buffs or others
    pool.sort(key=lambda s: -s.priority)
    return pool[0] if pool else None


def _trigger_ok(c, trigger: str) -> bool:
    if trigger in ("every_turn", "cooldown_ready", "sp_available", "passive"):
        return True
    if trigger == "hp_below_50":
        return c.hp <= c.max_hp * 0.5
    if trigger == "hp_below_30":
        return c.hp <= c.max_hp * 0.3
    return False


def _one_hit(attacker, defender, rng, events):
    """打一擊。回 True = 有命中。"""
    hit = rng.random() < hit_chance(attacker.effective_hit, defender.effective_flee)
    if not hit:
        events.append(AttackEvent(attacker.name, defender.name, 0, False, False))
        return False
    crit = rng.random() < crit_chance(attacker.effective_crit)
    mult, resist, race = elements.damage_mods(attacker, defender, None)
    if attacker.is_caster:
        from server.combat.formulas import magic_damage
        dmg = magic_damage(attacker.effective_matk, defender.effective_mdef,
                           element_multiplier=mult, soft_mdef=defender.soft_mdef,
                           resist_pct=resist, race_pct=race)
    else:
        dmg = physical_damage(attacker.effective_atk, defender.effective_defense,
                              element_multiplier=mult, soft_def=defender.soft_def,
                              resist_pct=resist, race_pct=race)
    if crit:
        dmg = round(dmg * CRIT_MULTIPLIER)
    defender.take_damage(dmg)
    events.append(AttackEvent(attacker.name, defender.name, dmg, crit, True))
    steal = attacker.procs.get("steal_loot", 0) if hasattr(attacker, "procs") else 0
    if steal and not any(getattr(e, "skill_id", "") == "steal" for e in events) \
            and rng.random() < steal / 100:
        from server.combat.events import SkillEvent
        events.append(SkillEvent(actor=attacker.name, target=defender.name,
                                 skill_id="steal", skill_name="偷竊"))
    return True


def _auto_attack(attacker, defender, rng, events):
    for _ in range(attacks_this_round(attacker.effective_aspd, rng)):
        if not defender.alive:
            break
        landed = _one_hit(attacker, defender, rng, events)
        # 二段攻擊：命中後依機率追加一擊
        extra = attacker.procs.get("extra_hit", 0) if hasattr(attacker, "procs") else 0
        if landed and extra and defender.alive and rng.random() < extra / 100:
            _one_hit(attacker, defender, rng, events)


def _take_turn(actor, foe, rng, events, min_sp_frac: float = 0.0):
    if actor.stunned:
        return
    skill = _pick_skill(actor, min_sp_frac)
    if skill and actor.spend_sp(skill.sp_cost):
        # cast_skill 內部按 effect 型別分流：heal_hp/buff 作用在 actor，其餘作用在 foe
        events += cast_skill(actor, foe, skill, rng)
        skill._cd_left = skill.cooldown_rounds
    else:
        _auto_attack(actor, foe, rng, events)


def simulate_fight(a, b, rng: random.Random, max_rounds: int = MAX_ROUNDS_DEFAULT,
                   flee_hp_frac: float = 0.0, *, a_potions: int = 0,
                   a_potion_heal: int = 0, a_potion_hp_frac: float = 0.0,
                   a_skill_min_sp_frac: float = 0.0) -> FightResult:
    events: list = []
    rounds = 0
    potions_used = 0

    def _predrink(actor):
        """輪到玩家行動前，血量低於門檻就連喝補品到門檻以上或喝完。"""
        nonlocal potions_used
        if actor is not a or a_potion_heal <= 0 or not a.alive:
            return
        healed = 0
        while potions_used < a_potions and a.hp < a.max_hp * a_potion_hp_frac:
            before = a.hp
            a.heal(a_potion_heal)
            healed += a.hp - before
            potions_used += 1
        if healed > 0:
            events.append(HealEvent(a.name, a.name, healed, source="potion"))

    # 先手：aspd 高者先，平手 a 先（吃得到場間留存的加速 buff）
    first, second = (a, b) if a.effective_aspd >= b.effective_aspd else (b, a)
    while a.alive and b.alive and rounds < max_rounds:
        rounds += 1
        for c in (first, second):
            tick_statuses(c, events)
            for s in c.skills:
                if s._cd_left > 0:
                    s._cd_left -= 1
        if not (a.alive and b.alive):
            break
        if flee_hp_frac > 0 and a.alive and a.hp < a.max_hp * flee_hp_frac:
            events.append(FledEvent(actor=a.name, hp=a.hp))
            return FightResult(None, None, "fled", rounds, a.hp, b.hp, events,
                               potions_used, _stole(events))
        _predrink(first)
        _take_turn(first, second, rng, events,
                   a_skill_min_sp_frac if first is a else 0.0)
        if second.alive:
            _predrink(second)
            _take_turn(second, first, rng, events,
                       a_skill_min_sp_frac if second is a else 0.0)

    if a.alive and b.alive:
        return FightResult(None, None, "stalemate", rounds, a.hp, b.hp, events,
                           potions_used, _stole(events))
    winner, loser = (a, b) if a.alive else (b, a)
    events.append(KillEvent(actor=winner.name, target=loser.name))
    return FightResult(winner.name, loser.name, "win", rounds, winner.hp,
                       loser.hp, events, potions_used, _stole(events))


def _stole(events) -> bool:
    return any(getattr(e, "skill_id", "") == "steal" for e in events)
