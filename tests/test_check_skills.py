from scripts.check_skills import check, check_skills


def test_current_skill_data_passes_checker():
    assert check() == []


def _jobs():
    return [
        {"id": "novice", "name": "新手", "parent_id": None, "skill_ids": []},
        {"id": "swordman", "name": "劍士", "parent_id": "novice", "skill_ids": ["bash"]},
        {"id": "mage", "name": "法師", "parent_id": "novice", "skill_ids": []},
    ]


def _ok_skill(**over):
    s = {
        "id": "bash", "name": "爆裂波動", "job_id": "swordman", "kind": "active",
        "max_level": 5, "sp_cost": [8, 9, 10, 11, 12],
        "effects": [{"type": "physical_hit", "power_pct": [1, 2, 3, 4, 5]}],
        "idle_default": {"trigger": "every_turn"},
    }
    s.update(over)
    return s


def test_baseline_fake_data_passes():
    assert check_skills([_ok_skill()], _jobs()) == []


def test_checker_catches_bad_sp_cost_length():
    errors = check_skills([_ok_skill(sp_cost=[8, 9, 10])], _jobs())
    assert any("sp_cost" in e for e in errors)


def test_checker_catches_bad_effect_type_element_and_list_length():
    bad = _ok_skill(effects=[{
        "type": "teleport", "element": "chaos", "power_pct": [1, 2],
    }])
    errors = check_skills([bad], _jobs())
    assert any("type" in e for e in errors)
    assert any("element" in e for e in errors)
    assert any("power_pct" in e for e in errors)


def test_checker_catches_passive_with_sp_and_bad_trigger():
    bad = _ok_skill(
        kind="passive", sp_cost=[0, 1, 0, 0, 0],
        effects=[{"type": "passive_stat", "stat": "atk", "amount": [1, 2, 3, 4, 5]}],
        idle_default={"trigger": "every_turn"},
    )
    errors = check_skills([bad], _jobs())
    assert sum("passive" in e for e in errors) >= 2


def test_checker_catches_skill_ids_mismatch():
    # 技能掛在 mage，但 swordman.skill_ids 仍列著 bash
    errors = check_skills([_ok_skill(job_id="mage")], _jobs())
    assert any("skill_ids" in e for e in errors)


def test_checker_catches_non_list_sp_cost():
    errors = check_skills([_ok_skill(sp_cost="12345")], _jobs())
    assert any("sp_cost" in e and "陣列" in e for e in errors)


def test_checker_catches_bad_requires_level():
    dep = _ok_skill(id="fire_bolt", job_id="mage", max_level=5)
    user = _ok_skill(id="cold_bolt", job_id="mage", requires={"fire_bolt": 99})
    jobs = _jobs()
    jobs[2]["skill_ids"] = ["fire_bolt", "cold_bolt"]
    jobs[1]["skill_ids"] = []
    errors = check_skills([dep, user], jobs)
    assert any("需求等級" in e for e in errors)


def test_checker_catches_bad_requires_chain():
    dep = _ok_skill(id="fire_bolt", job_id="mage")
    user = _ok_skill(id="bash", requires={"fire_bolt": 1})
    jobs = _jobs()
    jobs[1]["skill_ids"] = ["bash"]
    jobs[2]["skill_ids"] = ["fire_bolt"]
    errors = check_skills([dep, user], jobs)
    assert any("前置" in e for e in errors)
