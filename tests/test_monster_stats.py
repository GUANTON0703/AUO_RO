from server.content.monster_stats import baseline

# 校準目標（Pre-Renewal 手感）：
#  Lv1 glass（波利級）：HP 40~60、ATK 6~12、DEF 0
#  Lv1 之後大致線性偏指數，Lv50 normal 怪 HP 數千、ATK 數十


def test_lv1_glass_is_poring_ish():
    s = baseline(level=1, role="glass")
    assert 40 <= s.max_hp <= 60
    assert 5 <= s.atk <= 14
    assert s.defense == 0


def test_tank_has_more_hp_and_def_than_glass():
    g = baseline(level=20, role="glass")
    t = baseline(level=20, role="tank")
    assert t.max_hp > g.max_hp
    assert t.defense >= g.defense


def test_stats_increase_with_level():
    lo = baseline(level=5, role="normal")
    hi = baseline(level=45, role="normal")
    assert hi.max_hp > lo.max_hp * 5
    assert hi.atk > lo.atk


def test_boss_role_scales_hard():
    n = baseline(level=30, role="normal")
    b = baseline(level=30, role="boss")
    assert b.max_hp >= n.max_hp * 3


def test_returns_valid_combat_stats():
    from shared.content import CombatStats

    assert isinstance(baseline(level=10, role="normal"), CombatStats)
