import random

from server.combat.combatant import Combatant
from server.settlement.profile import estimate_fight_profile
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=2000, max_sp=200, atk=200, matk=10, defense=20,
                mdef=10, hit=120, flee=90, aspd=150, crit=10)
    base.update(kw)
    return Combatant(**base)


def test_profile_of_easy_monster():
    c = load_content()
    p = estimate_fight_profile(_hero(), c.get_monster("poring"), random.Random(0), samples=20)
    assert p.win_rate == 1.0
    assert p.avg_rounds >= 1
    assert p.avg_damage_taken >= 0


def test_profile_of_unwinnable_monster():
    c = load_content()
    weak = _hero(max_hp=200, atk=10, defense=0)
    p = estimate_fight_profile(weak, c.get_monster("curly_boar_king"), random.Random(1), samples=10)
    assert p.win_rate < 1.0


def test_profile_does_not_mutate_input():
    c = load_content()
    hero = _hero()
    estimate_fight_profile(hero, c.get_monster("wolf"), random.Random(2), samples=10)
    assert hero.hp == hero.max_hp
