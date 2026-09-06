from server.progression.stats import (
    STARTER_STAT_POINTS, raise_cost, total_earned_stat_points,
    points_spent_on, stat_points_available, STAT_MAX,
)


def test_raise_cost_pre_renewal():
    assert raise_cost(1) == 2
    assert raise_cost(9) == 2
    assert raise_cost(10) == 3
    assert raise_cost(50) == 7


def test_points_spent_from_1_to_value():
    assert points_spent_on(1) == 0
    assert points_spent_on(2) == 2
    assert points_spent_on(11) == sum(raise_cost(v) for v in range(1, 11))


def test_total_earned_grows_with_level():
    assert total_earned_stat_points(1) == STARTER_STAT_POINTS
    assert total_earned_stat_points(10) > total_earned_stat_points(1)


def test_available_points_math():
    stats = {"str": 5, "agi": 1, "vit": 1, "int": 1, "dex": 1, "luk": 1}
    avail = stat_points_available(base_level=10, stats=stats)
    spent = points_spent_on(5)
    assert avail == total_earned_stat_points(10) - spent


def test_stat_max_is_99():
    assert STAT_MAX == 99
