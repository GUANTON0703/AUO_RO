import random

from server.combat.combatant import Combatant, ResolvedSkill
from server.combat.skills import cast_skill


def _c(name, **kw):
    base = dict(name=name, max_hp=300, max_sp=100, atk=80, matk=60, defense=0,
                mdef=0, hit=60, flee=20, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_physical_hit_skill_damages_target():
    rng = random.Random(1)
    caster, target = _c("玩家"), _c("波利", max_hp=500, flee=0)
    rs = ResolvedSkill("bash", "爆裂波動", 3, "active", 9, 0,
                       [{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
                       "every_turn", 1)
    evs = cast_skill(caster, target, rs, rng)
    assert target.hp < 500
    assert any(e.kind == "skill" for e in evs)


def test_magic_hit_ignores_flee():
    rng = random.Random(2)
    caster, target = _c("法師", matk=100), _c("波利", max_hp=500, flee=999)
    rs = ResolvedSkill("fire_bolt", "火球", 2, "active", 12, 0,
                       [{"type": "magic_hit", "power_pct": [100, 150, 200, 250, 300],
                         "hits": [1, 2, 3, 4, 5]}], "every_turn", 1)
    evs = cast_skill(caster, target, rs, rng)
    assert target.hp < 500   # 必中


def test_heal_skill_restores_caster_hp():
    rng = random.Random(3)
    caster = _c("牧師", matk=50)
    caster.take_damage(200)
    rs = ResolvedSkill("heal", "治癒", 3, "active", 10, 0,
                       [{"type": "heal_hp", "matk_pct": [120, 160, 200, 240, 280]}],
                       "hp_below_50", 2)
    cast_skill(caster, caster, rs, rng)
    assert caster.hp > 100


def test_buff_applies_stat_mod():
    rng = random.Random(4)
    caster = _c("劍士")
    rs = ResolvedSkill("provoke", "挑釁", 2, "active", 8, 0,
                       [{"type": "buff", "stats": {"atk": [5, 10, 15, 20, 25]},
                         "duration_s": 60}], "every_turn", 1)
    cast_skill(caster, caster, rs, rng)
    assert caster.effective_atk > caster.atk


def test_passive_effect_is_noop():
    rng = random.Random(5)
    caster, target = _c("玩家"), _c("波利")
    rs = ResolvedSkill("sword_mastery", "劍術", 3, "passive", 0, 0,
                       [{"type": "passive_stat", "stat": "atk", "amount": [4, 8, 12, 16, 20]}],
                       "passive", 0)
    evs = cast_skill(caster, target, rs, rng)
    assert evs == []


def test_element_multiplier_and_resist_apply():
    from server.combat import elements
    # fire 對 earth = 1.5x（照 element_chart.json）
    fire_atk = _c("火法", matk=100, atk=1)
    earth_mob = _c("地怪", max_hp=99999, flee=0)
    earth_mob.element = "earth"
    water_mob = _c("水怪", max_hp=99999, flee=0)
    water_mob.element = "water"
    rs = ResolvedSkill("fb", "火球", 1, "active", 0, 0,
                       [{"type": "magic_hit", "element": "fire", "power_pct": [100]}],
                       "every_turn", 1)
    cast_skill(_c("火法", matk=100), earth_mob, rs, random.Random(1))
    cast_skill(_c("火法", matk=100), water_mob, rs, random.Random(1))
    assert (99999 - earth_mob.hp) > (99999 - water_mob.hp)  # 剋地 > 剋水

    resist_mob = _c("抗火怪", max_hp=99999, flee=0)
    resist_mob.element = "neutral"
    resist_mob.element_resist = {"fire": 50}
    plain_mob = _c("普通怪", max_hp=99999, flee=0)
    cast_skill(_c("火法", matk=100), resist_mob, rs, random.Random(1))
    cast_skill(_c("火法", matk=100), plain_mob, rs, random.Random(1))
    assert (99999 - resist_mob.hp) < (99999 - plain_mob.hp)


def test_envenom_applies_poison_dot():
    from server.combat.status import tick_statuses
    caster = _c("刺客", atk=100)
    target = _c("怪", max_hp=99999, flee=0)
    rs = ResolvedSkill("envenom", "毒擊", 3, "active", 12, 0,
                       [{"type": "physical_hit", "element": "poison",
                         "power_pct": [110, 130, 150, 170, 190], "debuff": "poison"}],
                       "every_turn", 1)
    cast_skill(caster, target, rs, random.Random(1))
    assert any(s.kind == "dot" for s in target.statuses)
    hp_before = target.hp
    tick_statuses(target, [])
    assert target.hp < hp_before  # 中毒每回合扣血
