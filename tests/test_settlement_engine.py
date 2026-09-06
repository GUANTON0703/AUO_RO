import random

from server.combat.combatant import Combatant
from server.settlement.config import HuntConfig
from server.settlement.engine import settle
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=3000, max_sp=300, atk=250, matk=10, defense=30,
                mdef=15, hit=140, flee=110, aspd=160, crit=12)
    base.update(kw)
    return Combatant(**base)


def test_offline_applies_efficiency_and_cap():
    c = load_content()
    poring = c.get_monster("poring")
    cfg = HuntConfig()
    r = settle(_hero(), poring, elapsed_seconds=100 * 3600, cfg=cfg,
               rng=random.Random(0), offline=True, pity_in={})
    assert r.real_elapsed_seconds == 100 * 3600
    assert abs(r.effective_seconds - 8 * 3600 * 0.6) < 1
    assert r.kills > 0
    assert r.base_exp == r.kills * poring.base_exp


def test_online_no_penalty():
    c = load_content()
    poring = c.get_monster("poring")
    r = settle(_hero(), poring, elapsed_seconds=30, cfg=HuntConfig(),
               rng=random.Random(0), offline=False, pity_in={})
    assert abs(r.effective_seconds - 30) < 0.01


def test_retreat_when_player_cannot_win():
    c = load_content()
    boss = c.get_monster("curly_boar_king")
    weak = _hero(max_hp=500, atk=40, defense=5)
    r = settle(weak, boss, elapsed_seconds=8 * 3600, cfg=HuntConfig(),
               rng=random.Random(1), offline=True, pity_in={},
               potion_item_id=None, potion_count=0)
    assert r.retreated is True
    assert r.effective_seconds < 8 * 3600 * 0.6


def test_potions_consumed_and_can_run_out():
    c = load_content()
    wolf = c.get_monster("wolf")
    squishy = _hero(max_hp=800, defense=5)
    r = settle(squishy, wolf, elapsed_seconds=4 * 3600, cfg=HuntConfig(),
               rng=random.Random(2), offline=True, pity_in={},
               potion_item_id="red_potion", potion_heal=350, potion_count=50)
    assert r.potions_used > 0
    if r.potions_used >= 50:
        assert r.retreated is True


def test_zeny_and_drops_accumulate():
    c = load_content()
    m = c.get_monster("green_cotton_worm")
    r = settle(_hero(), m, elapsed_seconds=3600, cfg=HuntConfig(),
               rng=random.Random(3), offline=True, pity_in={})
    assert r.zeny > 0
    assert sum(r.drops.values()) > 0


def test_deterministic():
    c = load_content()
    m = c.get_monster("poring")
    a = settle(_hero(), m, 3600, HuntConfig(), random.Random(7), offline=True, pity_in={})
    b = settle(_hero(), m, 3600, HuntConfig(), random.Random(7), offline=True, pity_in={})
    assert a.kills == b.kills and a.base_exp == b.base_exp and a.drops == b.drops


def test_events_include_kill_batch():
    c = load_content()
    m = c.get_monster("poring")
    r = settle(_hero(), m, 3600, HuntConfig(), random.Random(4), offline=True, pity_in={})
    assert any(e.kind == "kill_batch" for e in r.events)
