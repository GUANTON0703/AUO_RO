import random

from server.combat.combatant import Combatant, ResolvedSkill
from server.combat.engine import simulate_fight


def _mk(name, **kw):
    base = dict(name=name, max_hp=200, max_sp=50, atk=40, matk=5, defense=0,
                mdef=0, hit=50, flee=20, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_compound_skill_damage_hits_foe_not_self():
    # 同時有攻擊 + 自我 buff 的技能，攻擊要打敵人、buff 要加自己
    combo = ResolvedSkill(
        "war_cry", "戰吼", 3, "active", 5, 0,
        [{"type": "physical_hit", "power_pct": [150, 150, 150, 150, 150]},
         {"type": "buff", "stats": {"atk": [5, 10, 15, 20, 25]}, "duration_s": 60}],
        "every_turn", 5,
    )
    hero = _mk("英雄", atk=60, max_sp=30, skills=[combo])
    foe = _mk("怪", max_hp=400, flee=0)
    r = simulate_fight(hero, foe, rng=random.Random(0))
    assert foe.hp < 400            # 攻擊有打到敵人
    assert hero.effective_atk > 60  # buff 有生效
    # 沒有任何一筆「英雄打英雄」的傷害事件（複合技的攻擊分量不會誤傷自己）
    self_hits = [e for e in r.events
                 if getattr(e, "actor", None) == "英雄" and getattr(e, "target", None) == "英雄"
                 and e.kind in ("attack", "skill") and getattr(e, "damage", 0) > 0]
    assert self_hits == []


def test_stronger_combatant_wins():
    r = simulate_fight(_mk("強", atk=80, max_hp=500), _mk("弱", atk=10, max_hp=50),
                       rng=random.Random(0))
    assert r.winner == "強"
    assert r.rounds >= 1
    assert r.loser_hp == 0


def test_events_include_attacks_and_kill():
    r = simulate_fight(_mk("A", atk=60), _mk("B", max_hp=40), rng=random.Random(1))
    kinds = {e.kind for e in r.events}
    assert "attack" in kinds
    assert "kill" in kinds


def test_high_aspd_lands_more_hits_per_round():
    slow = simulate_fight(_mk("慢", aspd=100, atk=30), _mk("靶", max_hp=100000, flee=0),
                          rng=random.Random(2), max_rounds=5)
    fast = simulate_fight(_mk("快", aspd=300, atk=30), _mk("靶", max_hp=100000, flee=0),
                          rng=random.Random(2), max_rounds=5)
    slow_atks = sum(1 for e in slow.events if e.kind == "attack" and e.actor == "慢")
    fast_atks = sum(1 for e in fast.events if e.kind == "attack" and e.actor == "快")
    assert fast_atks > slow_atks


def test_stalemate_when_nobody_can_kill():
    r = simulate_fight(_mk("鐵", atk=1, max_hp=999), _mk("壁", atk=1, max_hp=999, defense=95),
                       rng=random.Random(3), max_rounds=50)
    assert r.outcome == "stalemate"


def test_skill_fires_by_trigger_and_costs_sp():
    bash = ResolvedSkill("bash", "爆裂波動", 5, "active", 10, 0,
                         [{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
                         "every_turn", 1)
    hero = _mk("英雄", atk=50, max_sp=30, skills=[bash])
    r = simulate_fight(hero, _mk("怪", max_hp=300, flee=0), rng=random.Random(4))
    assert any(e.kind == "skill" and e.skill_id == "bash" for e in r.events)
    assert hero.sp < 30   # 有消耗


def test_skill_min_sp_frac_holds_skills_until_sp_recovers():
    def _bash():
        return ResolvedSkill("bash", "爆裂波動", 1, "active", 12, 0,
                             [{"type": "physical_hit", "power_pct": [200]}],
                             "every_turn", 1)
    # 門檻 0：能放就放
    h1 = _mk("放招哥", atk=30, max_sp=40, skills=[_bash()])
    r1 = simulate_fight(h1, _mk("怪", max_hp=800, flee=0), rng=random.Random(4))
    free = sum(1 for e in r1.events if e.kind == "skill")
    # 門檻 0.9：SP 一低於 90% 就不放，整場幾乎只普攻
    h2 = _mk("省魔哥", atk=30, max_sp=40, skills=[_bash()])
    r2 = simulate_fight(h2, _mk("怪", max_hp=800, flee=0), rng=random.Random(4),
                        a_skill_min_sp_frac=0.9)
    gated = sum(1 for e in r2.events if e.kind == "skill")
    assert free > gated


def test_fight_flees_when_first_combatant_low():
    strong_boss = _mk("王", atk=200, max_hp=99999, defense=50)
    hero = _mk("勇者", atk=30, max_hp=1000)
    r = simulate_fight(hero, strong_boss, rng=random.Random(0), flee_hp_frac=0.3)
    assert r.outcome == "fled"
    assert hero.hp > 0
    assert hero.hp <= hero.max_hp * 0.35


def test_flee_disabled_fights_to_death():
    strong_boss = _mk("王", atk=200, max_hp=99999, defense=50)
    hero = _mk("勇者", atk=30, max_hp=1000)
    r = simulate_fight(hero, strong_boss, rng=random.Random(0), flee_hp_frac=0.0)
    assert r.outcome == "win"
    assert r.winner == "王"


def test_deterministic_with_same_seed():
    a1 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    a2 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    assert a1.rounds == a2.rounds and a1.winner == a2.winner


def test_double_attack_proc_adds_hits():
    plain = _mk("普通", atk=20, aspd=100)
    dbl = _mk("連擊", atk=20, aspd=100)
    dbl.procs = {"extra_hit": 100}          # 100% 觸發
    mob1 = _mk("怪A", max_hp=99999, flee=0, aspd=1)
    mob2 = _mk("怪B", max_hp=99999, flee=0, aspd=1)
    simulate_fight(plain, mob1, rng=random.Random(3), max_rounds=5)
    simulate_fight(dbl, mob2, rng=random.Random(3), max_rounds=5)
    assert (99999 - mob2.hp) > (99999 - mob1.hp) * 1.5


def test_sp_potion_drunk_when_sp_below_threshold():
    bash = ResolvedSkill("bash", "爆裂波動", 1, "active", 15, 0,
                         [{"type": "physical_hit", "power_pct": [200]}],
                         "every_turn", 1)
    hero = _mk("英雄", atk=30, max_hp=600, max_sp=30, skills=[bash])
    foe = _mk("怪", max_hp=1200, flee=0, atk=10)
    r = simulate_fight(hero, foe, rng=random.Random(4),
                       a_sp_potions=5, a_sp_potion_restore=20, a_sp_potion_frac=0.5)
    assert r.sp_potions_used > 0
    assert any(e.kind == "heal" and getattr(e, "source", "") == "sp_potion"
               for e in r.events)


def test_no_sp_potion_without_config():
    bash = ResolvedSkill("bash", "爆裂波動", 1, "active", 15, 0,
                         [{"type": "physical_hit", "power_pct": [200]}],
                         "every_turn", 1)
    hero = _mk("英雄", atk=30, max_hp=600, max_sp=30, skills=[bash])
    r = simulate_fight(hero, _mk("怪", max_hp=1200, flee=0, atk=10),
                       rng=random.Random(4))
    assert r.sp_potions_used == 0


def test_race_bonus_increases_damage():
    plain = _mk("普通", atk=50, aspd=100)
    slayer = _mk("剋星", atk=50, aspd=100)
    slayer.race_bonus = {"insect": 100}     # 對蟲 +100%
    bug1 = _mk("蟲A", max_hp=99999, flee=0, aspd=1)
    bug1.race = "insect"
    bug2 = _mk("蟲B", max_hp=99999, flee=0, aspd=1)
    bug2.race = "insect"
    simulate_fight(plain, bug1, rng=random.Random(4), max_rounds=3)
    simulate_fight(slayer, bug2, rng=random.Random(4), max_rounds=3)
    assert (99999 - bug2.hp) > (99999 - bug1.hp) * 1.5


def test_size_bonus_increases_damage():
    plain = _mk("普通", atk=50, aspd=100)
    hunter = _mk("大型剋星", atk=50, aspd=100)
    hunter.size_bonus = {"large": 100}     # 對大型 +100%
    big1 = _mk("大怪A", max_hp=99999, flee=0, aspd=1)
    big1.size = "large"
    big2 = _mk("大怪B", max_hp=99999, flee=0, aspd=1)
    big2.size = "large"
    simulate_fight(plain, big1, rng=random.Random(4), max_rounds=3)
    simulate_fight(hunter, big2, rng=random.Random(4), max_rounds=3)
    assert (99999 - big2.hp) > (99999 - big1.hp) * 1.5


def test_crit_bypasses_flee():
    # 100% 爆擊 vs 極高 FLEE：仍然每擊命中
    attacker = _mk("暴擊哥", crit=100, hit=1, aspd=100)
    dummy = _mk("閃避怪", flee=9999, max_hp=100000, atk=0)
    r = simulate_fight(attacker, dummy, rng=random.Random(0), max_rounds=30)
    hits = [e for e in r.events if getattr(e, "hit", False) and e.actor == "暴擊哥"]
    assert len(hits) >= 25  # 幾乎每回合都打到


def test_katar_crit_multiplier():
    from server.combat.formulas import CRIT_MULTIPLIER
    base = _mk("普通", crit=100, atk=100)
    katar = _mk("拳刃", crit=100, atk=100, crit_mult=2.0)
    dummy = lambda: _mk("木樁", flee=0, hit=0, atk=0, max_hp=1000000)
    r1 = simulate_fight(base, dummy(), rng=random.Random(1), max_rounds=5)
    r2 = simulate_fight(katar, dummy(), rng=random.Random(1), max_rounds=5)
    d1 = sum(e.damage for e in r1.events if getattr(e, "damage", 0) and e.actor == "普通")
    d2 = sum(e.damage for e in r2.events if getattr(e, "damage", 0) and e.actor == "拳刃")
    assert d2 > d1 * 1.3  # 2.0 vs 1.4 → 明顯更高
    assert CRIT_MULTIPLIER == 1.4
