BASE_LEVEL_CAP = 99
_JOB_CAP = {"novice": 10, "first": 50, "second": 50, "third": 70}


def job_level_cap(tier: str) -> int:
    return _JOB_CAP[tier]


def base_exp_for_next(level: int) -> int:
    """從 level 升到 level+1 所需經驗。曲線可延伸到 99+。"""
    return round(30 * level**2.4 + 40 * level + 30)


def job_exp_for_next(job_level: int, tier: str) -> int:
    mult = {"novice": 0.6, "first": 1.0, "second": 1.8, "third": 2.6}[tier]
    return round((20 * job_level**2.2 + 30 * job_level + 20) * mult)


def stat_points_at_level(level: int) -> int:
    return 2 + (level // 5)


def apply_base_exp(cur_level: int, cur_exp: int, amount: int):
    level, exp = cur_level, cur_exp + amount
    gained = 0
    while level < BASE_LEVEL_CAP and exp >= base_exp_for_next(level):
        exp -= base_exp_for_next(level)
        level += 1
        gained += stat_points_at_level(level)
    if level >= BASE_LEVEL_CAP:
        exp = 0
    return level, exp, gained


def apply_job_exp(cur_job_level: int, cur_job_exp: int, amount: int, tier: str):
    cap = job_level_cap(tier)
    level, exp = cur_job_level, cur_job_exp + amount
    gained = 0
    while level < cap and exp >= job_exp_for_next(level, tier):
        exp -= job_exp_for_next(level, tier)
        level += 1
        gained += 1
    if level >= cap:
        exp = 0
    return level, exp, gained
