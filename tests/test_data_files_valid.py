from server import content


def test_all_data_files_load_and_validate():
    c = content.load_content()
    assert len(c.monsters) >= 12
    assert len(c.maps) == 8
    assert len(c.items) >= 10


def test_every_map_has_monsters_in_its_level_range():
    c = content.load_content()
    for m in c.maps.values():
        lo, hi = m.level_range
        assert m.monster_ids, f"{m.id} 沒有怪"
        for mon in c.monsters_on_map(m.id):
            assert lo - 5 <= mon.level <= hi + 10, f"{mon.id} 等級偏離 {m.id} 的帶"


def test_element_chart_has_fire_earth_advantage():
    c = content.load_content()
    assert c.element_chart.multiplier("fire", "earth") > 1.0


def test_element_chart_ghost_and_holy_relations():
    c = content.load_content()
    chart = c.element_chart
    assert chart.multiplier("ghost", "ghost") > 1.0
    assert chart.multiplier("holy", "undead") > 1.0
    assert chart.multiplier("fire", "fire") < 1.0
    assert chart.multiplier("neutral", "ghost") < 1.0


def test_mvps_loaded_with_cooldown_and_home_map():
    c = content.load_content()
    assert len(c.mvps) >= 6
    for mvp in c.mvps.values():
        assert mvp.cooldown_hours >= 1
        assert mvp.home_map_id in c.maps
        assert mvp.is_mvp is True


def test_all_seven_starting_jobs_plus_second_tier():
    c = content.load_content()
    assert c.get_job("novice").tier == "novice"
    for j in ["swordman", "mage", "archer", "acolyte", "merchant", "thief"]:
        assert c.get_job(j).parent_id == "novice"
    for j in ["knight", "wizard", "hunter", "priest", "blacksmith", "assassin"]:
        assert c.get_job(j).tier == "second"


def test_each_first_job_has_five_skills():
    c = content.load_content()
    for j in ["swordman", "mage", "archer", "acolyte", "merchant", "thief"]:
        assert len(c.get_job(j).skill_ids) == 5
        for sid in c.get_job(j).skill_ids:
            assert c.skills[sid].job_id == j


def test_every_mvp_card_exists():
    c = content.load_content()
    for mvp in c.mvps.values():
        card_ids = [d.item_id for d in mvp.drops if d.item_id in c.cards]
        assert card_ids, f"{mvp.id} 沒有掉自己的卡"


def test_starter_weapon_per_job_buyable():
    c = content.load_content()
    weapons = [e for e in c.equipment.values() if e.slot == "weapon"]
    assert len(weapons) >= 6
