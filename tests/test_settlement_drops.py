import random

from server.settlement.config import HuntConfig
from server.settlement.drops import roll_drops
from shared.content import DropEntry


def _drops():
    return [
        DropEntry(item_id="jellopy", rate=0.7, min_qty=1, max_qty=2),
        DropEntry(item_id="card_x", rate=0.001),
    ]


def test_common_drop_roughly_matches_expectation_statistical():
    cfg = HuntConfig()
    got, pity = roll_drops(_drops(), kills=1000, rng=random.Random(0),
                           offline=True, pity_in={}, cfg=cfg)
    assert 800 <= got["jellopy"] <= 1300


def test_rare_drop_uses_binomial_offline():
    cfg = HuntConfig()
    totals = 0
    for seed in range(20):
        got, _ = roll_drops(_drops(), kills=2000, rng=random.Random(seed),
                            offline=True, pity_in={}, cfg=cfg)
        totals += got.get("card_x", 0)
    assert 15 <= totals <= 80


def test_pity_forces_drop_after_threshold():
    cfg = HuntConfig(card_pity_threshold=500)
    got, pity = roll_drops([DropEntry(item_id="card_x", rate=0.0001)],
                           kills=500, rng=random.Random(999),
                           offline=True, pity_in={"card_x": 0}, cfg=cfg)
    assert got.get("card_x", 0) >= 1
    assert pity["card_x"] < 500


def test_pity_counter_carries_when_no_drop():
    cfg = HuntConfig(card_pity_threshold=10000)
    got, pity = roll_drops([DropEntry(item_id="card_x", rate=0.0)],
                           kills=300, rng=random.Random(1),
                           offline=True, pity_in={"card_x": 50}, cfg=cfg)
    assert pity["card_x"] == 350


def test_online_mode_rolls_per_kill():
    cfg = HuntConfig()
    got, _ = roll_drops([DropEntry(item_id="jellopy", rate=1.0)], kills=5,
                        rng=random.Random(0), offline=False, pity_in={}, cfg=cfg)
    assert got["jellopy"] == 5
