import random

from server.combat.events import HealEvent, SkillEvent
from server.combat.formulas import (
    CRIT_MULTIPLIER, crit_chance, hit_chance, magic_damage, physical_damage,
)
from server.combat.status import Status, apply_status


def _seq(v, level: int):
    return v[min(level, len(v)) - 1] if isinstance(v, list) else v


def cast_skill(caster, target, skill, rng: random.Random) -> list:
    events: list = []
    for eff in skill.effects:
        t = eff.get("type")
        if t in ("physical_hit", "aoe"):
            events += _physical_skill(caster, target, skill, eff, rng)
        elif t == "magic_hit":
            events += _magic_skill(caster, target, skill, eff, rng)
        elif t == "heal_hp":
            events += _heal_skill(caster, skill, eff)
        elif t == "buff":
            _stat_mod_skill(caster, eff, skill.level, sign=1)
        elif t == "debuff":
            _stat_mod_skill(target, eff, skill.level, sign=-1)
        # proc / passive_stat：no-op
    return events


def _physical_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    total = 0
    for _ in range(hits):
        if rng.random() >= hit_chance(caster.effective_hit, target.effective_flee):
            continue
        dmg = physical_damage(round(caster.effective_atk * power), target.effective_defense)
        if rng.random() < crit_chance(caster.effective_crit):
            dmg = round(dmg * CRIT_MULTIPLIER)
        target.take_damage(dmg)
        total += dmg
    return [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                       skill_name=skill.name, damage=total)]


def _magic_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    total = 0
    for _ in range(hits):
        dmg = magic_damage(round(caster.effective_matk * power), target.effective_mdef)
        target.take_damage(dmg)
        total += dmg
    return [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                       skill_name=skill.name, damage=total)]


def _heal_skill(caster, skill, eff):
    if "flat" in eff:
        amount = _seq(eff["flat"], skill.level)
    else:
        amount = round(caster.effective_matk * _seq(eff.get("matk_pct", 100), skill.level) / 100)
    caster.heal(amount)
    return [HealEvent(actor=caster.name, target=caster.name, amount=amount)]


def _stat_mod_skill(who, eff, level, sign):
    dur = max(1, round(eff.get("duration_s", 60) / 2))
    stats = eff.get("stats", {})
    for stat, seq in stats.items():
        mag = _seq(seq, level) * sign
        apply_status(who, Status(kind="stat_mod", name=f"{stat}_mod", duration=dur,
                                 magnitude=mag, stat=stat))
