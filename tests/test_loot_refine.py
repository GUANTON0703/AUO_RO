import random

from server.loot.refine import (
    REFINE_CAP, success_rate, refine_ore_for, refine_zeny_cost, attempt_refine,
    attempt_random_refine,
)


def test_success_rate_table():
    assert success_rate(0) == 1.0
    assert success_rate(3) == 1.0
    assert success_rate(4) == 0.6
    assert success_rate(9) == 0.1
    assert success_rate(REFINE_CAP) == 0.0


def test_ore_by_slot():
    assert refine_ore_for("weapon") == "oridecon"
    assert refine_ore_for("armor") == "elunium"
    assert refine_ore_for("shoes") == "elunium"


def test_zeny_cost_scales():
    assert refine_zeny_cost(0) < refine_zeny_cost(7)


def test_attempt_refine_safe_levels_always_succeed():
    for start in range(0, 4):
        new, ok = attempt_refine(start, rng=random.Random(0))
        assert ok is True and new == start + 1


def test_attempt_refine_failure_downgrades():
    fails = 0
    for seed in range(50):
        new, ok = attempt_refine(9, rng=random.Random(seed))
        if not ok:
            assert new == 8
            fails += 1
    assert fails > 20


def test_cannot_downgrade_below_zero():
    new, ok = attempt_refine(0, rng=random.Random(0))
    assert new == 1


def test_attempt_random_refine_uses_weighted_increment_boundaries():
    class FixedRng:
        def __init__(self, value):
            self.value = value

        def random(self):
            return self.value

    assert attempt_random_refine(4, rng=FixedRng(0.00)) == (4, 0)
    assert attempt_random_refine(4, rng=FixedRng(0.10)) == (5, 1)
    assert attempt_random_refine(4, rng=FixedRng(0.60)) == (6, 2)
    assert attempt_random_refine(4, rng=FixedRng(0.95)) == (7, 3)


def test_attempt_random_refine_caps_at_maximum():
    class FixedRng:
        def random(self):
            return 0.99

    assert attempt_random_refine(9, rng=FixedRng()) == (REFINE_CAP, 1)
