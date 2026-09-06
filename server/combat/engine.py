import random
from dataclasses import dataclass, field

from server.combat.events import AttackEvent, KillEvent
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
    outcome: str            # "win" / "stalemate"
    rounds: int
    winner_hp: int
    loser_hp: int
    events: list = field(default_factory=list)


def _pick_skill(c):
    ready = []
    for s in c.skills:
        if s.kind != "active" or s._cd_left > 0 or c.sp < s.sp_cost:
            continue
        if _trigger_ok(c, s.trigger):
            ready.append(s)
    ready.sort(key=lambda s: -s.priority)
    return ready[0] if ready else None


def _trigger_ok(c, trigger: str) -> bool:
    if trigger in ("every_turn", "cooldown_ready", "sp_available", "passive"):
        return True
    if trigger == "hp_below_50":
        return c.hp <= c.max_hp * 0.5
    if trigger == "hp_below_30":
        return c.hp <= c.max_hp * 0.3
    return False


def _auto_attack(attacker, defender, rng, events):
    for _ in range(attacks_this_round(attacker.aspd, rng)):
        if not defender.alive:
            break
        hit = rng.random() < hit_chance(attacker.effective_hit, defender.effective_flee)
        if not hit:
            events.append(AttackEvent(attacker.name, defender.name, 0, False, False))
            continue
        crit = rng.random() < crit_chance(attacker.effective_crit)
        base = attacker.effective_matk if attacker.is_caster else attacker.effective_atk
        dmg = physical_damage(base, defender.effective_defense)
        if crit:
            dmg = round(dmg * CRIT_MULTIPLIER)
        defender.take_damage(dmg)
        events.append(AttackEvent(attacker.name, defender.name, dmg, crit, True))


def _take_turn(actor, foe, rng, events):
    if actor.stunned:
        return
    skill = _pick_skill(actor)
    if skill and actor.spend_sp(skill.sp_cost):
        # cast_skill 內部按 effect 型別分流：heal_hp/buff 作用在 actor，其餘作用在 foe
        events += cast_skill(actor, foe, skill, rng)
        skill._cd_left = skill.cooldown_rounds
    else:
        _auto_attack(actor, foe, rng, events)


def simulate_fight(a, b, rng: random.Random, max_rounds: int = MAX_ROUNDS_DEFAULT) -> FightResult:
    events: list = []
    rounds = 0
    # 先手：aspd 高者先，平手 a 先
    first, second = (a, b) if a.aspd >= b.aspd else (b, a)
    while a.alive and b.alive and rounds < max_rounds:
        rounds += 1
        for c in (first, second):
            tick_statuses(c, events)
            for s in c.skills:
                if s._cd_left > 0:
                    s._cd_left -= 1
        if not (a.alive and b.alive):
            break
        _take_turn(first, second, rng, events)
        if second.alive:
            _take_turn(second, first, rng, events)

    if a.alive and b.alive:
        return FightResult(None, None, "stalemate", rounds, a.hp, b.hp, events)
    winner, loser = (a, b) if a.alive else (b, a)
    events.append(KillEvent(actor=winner.name, target=loser.name))
    return FightResult(winner.name, loser.name, "win", rounds, winner.hp, loser.hp, events)
