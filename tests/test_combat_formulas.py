import random

from server.combat import formulas as f


def test_physical_damage_defense_has_diminishing_returns():
    assert f.physical_damage(atk=100, target_defense=0) == 100
    assert f.physical_damage(atk=100, target_defense=70) == 50    # def/(def+70) = 50%
    # 高防禦仍會被打到（不再夾死在 95%）
    assert 30 <= f.physical_damage(atk=100, target_defense=100) <= 45
    assert f.physical_damage(atk=100, target_defense=300) > 10


def test_physical_damage_floor_is_one():
    assert f.physical_damage(atk=1, target_defense=95) == 1


def test_magic_damage_uses_mdef():
    assert f.magic_damage(matk=200, target_mdef=70) == 100


def test_hit_chance_formula():
    assert f.hit_chance(attacker_hit=50, target_flee=50) == 0.80
    assert f.hit_chance(attacker_hit=70, target_flee=50) == 0.95  # clamp 上限
    assert f.hit_chance(attacker_hit=0, target_flee=200) == 0.05  # clamp 下限


def test_crit_chance_clamped_fraction():
    assert f.crit_chance(20) == 0.20
    assert f.crit_chance(150) == 1.0
    assert f.crit_chance(-5) == 0.0


def test_element_multiplier_defaults_to_one():
    assert f.physical_damage(atk=100, target_defense=0, element_multiplier=1.0) == 100
    assert f.physical_damage(atk=100, target_defense=0, element_multiplier=2.0) == 200


def test_attacks_this_round_from_aspd():
    rng = random.Random(0)
    # aspd 100 → 每回合剛好 1 次
    assert all(f.attacks_this_round(100, rng) == 1 for _ in range(20))
    # 攻速上限 193 → 剛好 3 次
    assert all(f.attacks_this_round(193, rng) == 3 for _ in range(20))
    # aspd 147（約 2 擊點）→ 平均接近 2
    xs = [f.attacks_this_round(147, rng) for _ in range(3000)]
    assert set(xs) <= {1, 2, 3}
    assert 1.9 < sum(xs) / len(xs) < 2.1
