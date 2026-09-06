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
