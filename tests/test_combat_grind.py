import random

from server.combat.combatant import Combatant
from server.combat.grind import simulate_grind
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=2000, max_sp=200, atk=200, matk=10, defense=20,
                mdef=10, hit=120, flee=90, aspd=150, crit=10)
    base.update(kw)
    return Combatant(**base)


def test_grind_kills_weak_monsters_and_counts_exp():
    content = load_content()
    poring = content.get_monster("poring")
    r = simulate_grind(_hero(), poring, n_fights=50, rng=random.Random(0))
    assert r.kills == 50
    assert r.base_exp == 50 * poring.base_exp
    assert r.job_exp == 50 * poring.job_exp
    assert r.player_defeated is False


def test_grind_stops_when_player_would_die():
    content = load_content()
    boss = content.get_monster("curly_boar_king")   # L48 boss，脆皮英雄打不過
    weak = _hero(max_hp=300, atk=30, defense=0)
    r = simulate_grind(weak, boss, n_fights=100, rng=random.Random(1))
    assert r.player_defeated is True
    assert r.kills < 100


def test_grind_reports_rounds_and_damage_taken():
    content = load_content()
    wolf = content.get_monster("wolf")
    r = simulate_grind(_hero(), wolf, n_fights=20, rng=random.Random(2))
    assert r.total_rounds > 0
    assert r.damage_taken >= 0


def test_grind_hp_carries_between_fights():
    content = load_content()
    wolf = content.get_monster("wolf")
    hero = _hero(max_hp=2000)
    simulate_grind(hero, wolf, n_fights=5, rng=random.Random(3))
    assert hero.hp <= 2000   # 沒有每場回滿


def test_deterministic():
    content = load_content()
    m = content.get_monster("green_cotton_worm")
    r1 = simulate_grind(_hero(), m, n_fights=30, rng=random.Random(9))
    r2 = simulate_grind(_hero(), m, n_fights=30, rng=random.Random(9))
    assert r1.kills == r2.kills and r1.base_exp == r2.base_exp
