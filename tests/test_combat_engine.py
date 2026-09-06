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


def test_deterministic_with_same_seed():
    a1 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    a2 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    assert a1.rounds == a2.rounds and a1.winner == a2.winner
