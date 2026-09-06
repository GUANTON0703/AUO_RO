from server.progression.levels import stat_points_at_level

STARTER_STAT_POINTS = 48
STAT_MAX = 99
STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")


def raise_cost(current_value: int) -> int:
    return (current_value // 10) + 2


def points_spent_on(value: int) -> int:
    return sum(raise_cost(v) for v in range(1, value))


def total_earned_stat_points(base_level: int) -> int:
    return STARTER_STAT_POINTS + sum(stat_points_at_level(l) for l in range(2, base_level + 1))


def points_spent(stats: dict) -> int:
    return sum(points_spent_on(stats[k]) for k in STAT_KEYS)


def stat_points_available(base_level: int, stats: dict) -> int:
    return total_earned_stat_points(base_level) - points_spent(stats)
