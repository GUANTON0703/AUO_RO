import random

from server import settlement
from server.combat.combatant import Combatant
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=3000, max_sp=300, atk=250, matk=10, defense=30,
                mdef=15, hit=140, flee=110, aspd=160, crit=12)
    base.update(kw)
    return Combatant(**base)


def test_public_api():
    assert hasattr(settlement, "settle")
    assert hasattr(settlement, "HuntConfig")
    assert hasattr(settlement, "SettlementResult")


def test_full_offline_session_on_real_map_monster():
    c = load_content()
    r = settlement.settle(_hero(), c.get_monster("raccoon"),
                          elapsed_seconds=6 * 3600, cfg=settlement.HuntConfig(),
                          rng=random.Random(0), offline=True, pity_in={},
                          potion_item_id="red_potion", potion_heal=45, potion_count=500)
    assert r.kills > 100
    assert r.base_exp > 0 and r.zeny > 0
    assert not r.retreated


def test_card_can_drop_over_long_session():
    c = load_content()
    total_cards = 0
    for seed in range(5):
        r = settlement.settle(_hero(), c.get_monster("poring"),
                              elapsed_seconds=8 * 3600, cfg=settlement.HuntConfig(),
                              rng=random.Random(seed), offline=True, pity_in={})
        total_cards += r.drops.get("poring_card", 0)
    assert total_cards >= 1


def test_pity_counter_round_trips_across_sessions():
    c = load_content()
    poring = c.get_monster("poring")
    pity: dict = {}
    for _ in range(3):
        r = settlement.settle(_hero(), poring, elapsed_seconds=1 * 3600,
                              cfg=settlement.HuntConfig(),
                              rng=random.Random(42), offline=True, pity_in=pity)
        pity = r.pity_out
    assert "poring_card" in pity
    assert pity["poring_card"] < settlement.HuntConfig().card_pity_threshold
