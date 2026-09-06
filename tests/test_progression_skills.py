from server.progression.skills import skill_points_available, can_learn


def test_skill_points_from_job_level_minus_learned():
    learned = {"bash": 3, "provoke": 1}
    avail = skill_points_available(job_level=10, learned=learned, carried=0)
    assert avail == (10 - 1) - 4


def test_carried_points_from_previous_job():
    avail = skill_points_available(job_level=1, learned={}, carried=9)
    assert avail == 9


def test_can_learn_checks_job_and_points():
    from server.content import load_content
    c = load_content()
    ok, reason = can_learn(c, character_job="swordman", skill_id="bash",
                           target_level=1, current_learned={}, points_available=5)
    assert ok is True
    bad, _ = can_learn(c, character_job="mage", skill_id="bash", target_level=1,
                       current_learned={}, points_available=5)
    assert bad is False


def test_cannot_exceed_skill_max_level():
    from server.content import load_content
    c = load_content()
    maxlv = c.skills["bash"].max_level
    ok, _ = can_learn(c, "swordman", "bash", target_level=maxlv + 1,
                      current_learned={}, points_available=99)
    assert ok is False


def test_not_enough_points():
    from server.content import load_content
    c = load_content()
    ok, _ = can_learn(c, "swordman", "bash", target_level=3,
                      current_learned={}, points_available=1)
    assert ok is False
