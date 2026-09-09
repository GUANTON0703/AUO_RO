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


class SeqRng:
    def __init__(self, *vals):
        self.vals = list(vals)

    def random(self):
        return self.vals.pop(0)


def test_attempt_random_refine_stage_one_failure_downgrades():
    # refine 4 成功率 0.6，第一段 roll 0.7 → 判定失敗、降一級、增量 0
    assert attempt_random_refine(4, rng=SeqRng(0.70)) == (3, False, 0)


def test_attempt_random_refine_stage_two_weighted_increments():
    # 第一段 roll 0.0 過，第二段抽增量
    assert attempt_random_refine(4, rng=SeqRng(0.0, 0.00)) == (4, True, 0)
    assert attempt_random_refine(4, rng=SeqRng(0.0, 0.10)) == (5, True, 1)
    assert attempt_random_refine(4, rng=SeqRng(0.0, 0.60)) == (6, True, 2)
    assert attempt_random_refine(4, rng=SeqRng(0.0, 0.95)) == (7, True, 3)


def test_attempt_random_refine_caps_at_maximum():
    assert attempt_random_refine(9, rng=SeqRng(0.0, 0.99)) == (REFINE_CAP, True, 1)
