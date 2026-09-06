import random

from server.combat.combatant import Combatant, ResolvedSkill
from server.settlement.config import HuntConfig
from server.settlement.engine import settle
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=3000, max_sp=300, atk=250, matk=10, defense=30,
                mdef=15, hit=140, flee=110, aspd=160, crit=12)
    base.update(kw)
    return Combatant(**base)


def test_short_offline_session_no_phantom_potions():
    # 5 分鐘離線打會掉血的怪，初始滿血緩衝夠 → 不該消耗補品
    c = load_content()
    r = settle(_hero(max_hp=3000, defense=10), c.get_monster("wolf"),
               elapsed_seconds=300, cfg=HuntConfig(), rng=random.Random(0),
               offline=True, pity_in={}, potion_item_id="rp", potion_heal=45,
               potion_count=500)
    assert r.potions_used == 0
    assert r.retreated is False


def test_partial_winrate_retreats_early_by_death():
    # 勉強能贏但常輸的對戰 → 幾何分布，撐不了整場 8h
    c = load_content()
    marginal = _hero(max_hp=1400, atk=120, defense=8, flee=40)
    r = settle(marginal, c.get_monster("wolf"), elapsed_seconds=8 * 3600,
               cfg=HuntConfig(), rng=random.Random(3), offline=True, pity_in={},
               potion_item_id="rp", potion_heal=45, potion_count=9999)
    if 0.0 < _wr(marginal, c) < 1.0:
        assert r.retreated is True


def _wr(player, content):
    from server.settlement.profile import estimate_fight_profile
    return estimate_fight_profile(player, content.get_monster("wolf"),
                                  random.Random(3), samples=20).win_rate


def _skill_hero():
    c = load_content()
    bash_def = c.skills["bash"]
    bash = ResolvedSkill(
        skill_id="bash", name=bash_def.name, level=1, kind="active",
        sp_cost=5, cooldown_rounds=0, effects=bash_def.effects,
        trigger="every_turn", priority=3,
    )
    return _hero(skills=[bash])


# ---------------------------------------------------------------- Task 5：統計路徑

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


# ---------------------------------------------------------------- Task 6：逐場路徑

def test_online_literal_path_matches_kills_roughly():
    c = load_content()
    poring = c.get_monster("poring")
    r = settle(_hero(), poring, elapsed_seconds=60, cfg=HuntConfig(),
               rng=random.Random(0), offline=False, pity_in={})
    assert 1 <= r.kills <= 30
    assert r.base_exp == r.kills * poring.base_exp


def test_online_sp_regen_between_fights():
    c = load_content()
    poring = c.get_monster("poring")
    # 一個帶耗 SP 技能的英雄，長時間在線：有場間 SP 回復時，SP 不會被抽乾。
    with_regen = settle(_skill_hero(), poring, elapsed_seconds=1000,
                        cfg=HuntConfig(sp_regen_per_sec=1.0),
                        rng=random.Random(0), offline=False, pity_in={})
    no_regen = settle(_skill_hero(), poring, elapsed_seconds=1000,
                      cfg=HuntConfig(sp_regen_per_sec=0.0),
                      rng=random.Random(0), offline=False, pity_in={})
    assert with_regen.kills == no_regen.kills  # 場數一樣，差在 SP 狀態
    assert no_regen.final_sp == 0              # 沒回復 → 被技能抽乾
    assert with_regen.final_sp > 100           # 有回復 → SP 撐住


def test_online_and_offline_expected_values_align():
    c = load_content()
    m = c.get_monster("green_cotton_worm")
    hero = _hero()
    on = settle(hero, m, 3600, HuntConfig(), random.Random(1), offline=False, pity_in={})
    off = settle(hero, m, 3600, HuntConfig(), random.Random(1), offline=True, pity_in={})
    ratio = off.kills / max(1, on.kills)
    assert 0.4 < ratio < 0.85


def test_online_settlement_includes_combat_events():
    c = load_content()
    r = settle(_hero(), c.get_monster("green_cotton_worm"), elapsed_seconds=40,
               cfg=HuntConfig(), rng=random.Random(0), offline=False, pity_in={})
    kinds = {e.kind for e in r.events}
    assert "attack" in kinds or "skill" in kinds
    assert "kill" in kinds
    assert any(e.kind == "kill_batch" for e in r.events)


def test_offline_settlement_has_no_per_round_events():
    c = load_content()
    r = settle(_hero(), c.get_monster("poring"), elapsed_seconds=3600,
               cfg=HuntConfig(), rng=random.Random(0), offline=True, pity_in={})
    assert not any(e.kind in ("attack", "skill") for e in r.events)
