import random

from server.combat import elements
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
        if t == "physical_hit":
            events += _physical_skill(caster, target, skill, eff, rng)
        elif t == "aoe":
            # 範圍技：施法職走魔法傷害，其餘走物理（magnum break 之類）
            fn = _magic_skill if caster.is_caster else _physical_skill
            events += fn(caster, target, skill, eff, rng)
        elif t == "magic_hit":
            events += _magic_skill(caster, target, skill, eff, rng)
        elif t == "heal_hp":
            events += _heal_skill(caster, skill, eff)
        elif t == "buff":
            _stat_mod_skill(caster, eff, skill.level, skill.name)
            events.append(SkillEvent(actor=caster.name, target=caster.name,
                                     skill_id=skill.skill_id, skill_name=skill.name))
        elif t == "debuff":
            _stat_mod_skill(target, eff, skill.level, skill.name)
            events.append(SkillEvent(actor=caster.name, target=target.name,
                                     skill_id=skill.skill_id, skill_name=skill.name))
        elif t == "proc":
            events += _proc_skill(caster, target, skill, eff, rng)
        # passive_stat：no-op
    return events


def _apply_poison(target, level: int, events: list) -> None:
    per_tick = round(target.max_hp * 0.015) + level * 3
    fresh = not any(s.name == "poison" for s in target.statuses)
    apply_status(target, Status(kind="dot", name="poison", duration=4,
                                magnitude=per_tick))
    if fresh:
        events.append(SkillEvent(actor="", target=target.name, skill_id="poison",
                                 skill_name="中毒"))


def _physical_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    element = eff.get("element")
    mult, resist, race = elements.damage_mods(caster, target, element)
    total = landed = 0
    for _ in range(hits):
        crit = rng.random() < crit_chance(caster.effective_crit)
        if not crit and rng.random() >= max(
                hit_chance(caster.effective_hit, target.effective_flee),
                caster.min_hit_chance):
            continue
        landed += 1
        dmg = physical_damage(round(caster.effective_atk * power), target.effective_defense,
                              element_multiplier=mult, soft_def=target.soft_def,
                              resist_pct=resist, race_pct=race)
        if crit:
            dmg = round(dmg * getattr(caster, "crit_mult", CRIT_MULTIPLIER))
        target.take_damage(dmg)
        total += dmg
    out = [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                      skill_name=skill.name, damage=total)]
    if landed and eff.get("debuff") == "poison":
        _apply_poison(target, skill.level, out)
    return out


def _magic_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    mult, resist, race = elements.damage_mods(caster, target, eff.get("element"))
    total = 0
    for _ in range(hits):
        dmg = magic_damage(round(caster.effective_matk * power), target.effective_mdef,
                           element_multiplier=mult, soft_mdef=target.soft_mdef,
                           resist_pct=resist, race_pct=race)
        target.take_damage(dmg)
        total += dmg
    return [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                       skill_name=skill.name, damage=total)]


def _proc_skill(caster, target, skill, eff, rng):
    """主動 proc 技能（steal）。extra_hit 型走被動路線，這裡不處理。"""
    chance = _seq(eff.get("chance_pct", 0), skill.level)
    if eff.get("effect") == "steal_loot" and rng.random() < chance / 100:
        return [SkillEvent(actor=caster.name, target=target.name, skill_id="steal",
                           skill_name=skill.name)]
    return []


def _heal_skill(caster, skill, eff):
    if "flat" in eff:
        amount = _seq(eff["flat"], skill.level)
    else:
        amount = round(caster.effective_matk * _seq(eff.get("matk_pct", 100), skill.level) / 100)
    caster.heal(amount)
    return [HealEvent(actor=caster.name, target=caster.name, amount=amount)]


def _stat_mod_skill(who, eff, level, source=""):
    """buff 格式 {stats:{stat:[...]}}；debuff 格式 {stat, pct:[...]}（值本身已帶正負）。"""
    dur = max(1, round(eff.get("duration_s", 60) / 2))
    if "stats" in eff:
        pairs = list(eff["stats"].items())
    else:
        pairs = [(eff["stat"], eff.get("pct", eff.get("amount", [0])))]
    for stat, seq in pairs:
        apply_status(who, Status(kind="stat_mod", name=f"{stat}_mod", duration=dur,
                                 magnitude=_seq(seq, level), stat=stat, source=source))
