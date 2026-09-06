import random

from server.settlement.events import FindMonsterEvent, FlyWingEvent, BossRetreatEvent
from server.settlement.strategy import HuntStrategy, choose_hunt_event


def test_strategy_accepts_target_filters_and_item_policies():
    strategy = HuntStrategy(
        include_monsters=["poring", "lunatic"],
        exclude_monsters=["boss"],
        flee_on_boss=True,
        auto_potion=True,
        potion_item_id="red_potion",
        buy_potions=True,
        sell_items=True,
    )
    assert strategy.include_monsters == ["poring", "lunatic"]
    assert strategy.flee_on_boss is True
    assert strategy.buy_potions is True


def test_random_event_rolls_are_deterministic_and_testable():
    cfg = type("Config", (), {"find_monster_rate": 1.0, "fly_wing_rate": 0.0,
                               "boss_retreat_rate": 0.0})()
    event = choose_hunt_event(is_boss=False, rng=random.Random(1), cfg=cfg)
    assert isinstance(event, FindMonsterEvent)

    cfg = type("Config", (), {"find_monster_rate": 0.0, "fly_wing_rate": 1.0,
                               "boss_retreat_rate": 0.0})()
    assert isinstance(choose_hunt_event(False, random.Random(1), cfg), FlyWingEvent)

    cfg = type("Config", (), {"find_monster_rate": 0.0, "fly_wing_rate": 0.0,
                               "boss_retreat_rate": 1.0})()
    assert isinstance(choose_hunt_event(True, random.Random(1), cfg), BossRetreatEvent)
