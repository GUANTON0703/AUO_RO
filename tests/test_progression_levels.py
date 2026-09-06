from server.progression.levels import (
    base_exp_for_next, job_exp_for_next, apply_base_exp, apply_job_exp,
    BASE_LEVEL_CAP, job_level_cap,
)


def test_exp_curve_is_increasing():
    assert base_exp_for_next(1) < base_exp_for_next(10) < base_exp_for_next(40)


def test_base_level_cap_is_50_in_v1():
    assert BASE_LEVEL_CAP == 50


def test_job_level_cap_by_tier():
    assert job_level_cap("novice") == 10
    assert job_level_cap("first") == 50
    assert job_level_cap("second") == 70


def test_apply_base_exp_single_levelup():
    need = base_exp_for_next(1)
    lv, exp, gained_stat_pts = apply_base_exp(cur_level=1, cur_exp=0, amount=need)
    assert lv == 2
    assert exp == 0
    assert gained_stat_pts == (2 + 2 // 5)


def test_apply_base_exp_multi_levelup_and_remainder():
    total = base_exp_for_next(1) + base_exp_for_next(2) + 5
    lv, exp, _ = apply_base_exp(cur_level=1, cur_exp=0, amount=total)
    assert lv == 3
    assert exp == 5


def test_apply_base_exp_stops_at_cap():
    lv, exp, _ = apply_base_exp(cur_level=49, cur_exp=0, amount=10**12)
    assert lv == 50
    assert exp == 0


def test_apply_job_exp_gives_skill_points():
    need = job_exp_for_next(1, "first")
    jl, jexp, skill_pts = apply_job_exp(cur_job_level=1, cur_job_exp=0,
                                        amount=need, tier="first")
    assert jl == 2
    assert skill_pts == 1
