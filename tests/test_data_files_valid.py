from server import content


def test_all_data_files_load_and_validate():
    c = content.load_content()
    assert len(c.monsters) >= 12
    assert len(c.maps) >= 13
    assert len(c.items) >= 10


def test_every_map_has_monsters_in_its_level_range():
    c = content.load_content()
    for m in c.maps.values():
        lo, hi = m.level_range
        assert m.monster_ids, f"{m.id} 沒有怪"
        for mon in c.monsters_on_map(m.id):
            assert lo - 5 <= mon.level <= hi + 10, f"{mon.id} 等級偏離 {m.id} 的帶"


def test_every_equipment_obtainable():
    c = content.load_content()
    drop_ids = set()
    for owner in list(c.monsters.values()) + list(c.mvps.values()):
        drop_ids.update(d.item_id for d in owner.drops)
    for eq in c.equipment.values():
        assert eq.npc_buy is not None or eq.id in drop_ids, f"{eq.id} 無取得來源"


def test_level_curve_has_no_gap():
    c = content.load_content()
    levels = [m.level for m in c.monsters.values()]
    for lo in range(1, 50, 5):
        hi = lo + 4
        assert any(lo <= lv <= hi for lv in levels), f"等級 {lo}-{hi} 沒有可打的怪"


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


def test_first_job_skill_ids_match_skills_json():
    c = content.load_content()
    for j in ["swordman", "mage", "archer", "acolyte", "merchant", "thief"]:
        declared = set(c.get_job(j).skill_ids)
        actual = {s.id for s in c.skills.values() if s.job_id == j}
        assert declared == actual, j
        assert len(declared) >= 5


def test_every_mvp_card_exists():
    c = content.load_content()
    for mvp in c.mvps.values():
        card_ids = [d.item_id for d in mvp.drops if d.item_id in c.cards]
        assert card_ids, f"{mvp.id} 沒有掉自己的卡"


def test_mvp_beatable_by_geared_same_level_player():
    import random

    from server.combat import simulate_fight
    from server.combat.combatant import Combatant
    from server.progression import (
        CharacterSnapshot, EquippedPiece, build_player_combatant,
    )
    c = content.load_content()
    for mvp in c.mvps.values():
        lv = mvp.level
        hero = build_player_combatant(CharacterSnapshot(
            name="P", job_id="swordman", base_level=lv, job_level=min(lv, 50),
            stats={"str": lv + 20, "agi": lv // 2, "vit": lv, "int": 5,
                   "dex": lv, "luk": lv // 3},
            learned_skills={"bash": 5},
            equipped=[EquippedPiece("blade", 5, []), EquippedPiece("cotton_shirt", 5, [])],
        ), c)
        r = simulate_fight(hero, Combatant.from_monster(mvp), rng=random.Random(0),
                           max_rounds=300)
        assert r.winner == hero.name, f"{mvp.name} 同級養好的劍士打不贏"
        assert 10 <= r.rounds <= 250, f"{mvp.name} 戰鬥 {r.rounds} 回合，不在合理範圍"


def test_starter_weapon_per_job_buyable():
    c = content.load_content()
    weapons = [e for e in c.equipment.values() if e.slot == "weapon"]
    assert len(weapons) >= 6


def test_lv60_classic_batch_one_maps_and_cards_exist():
    c = content.load_content()
    for map_id in ("sunken_ship_1f", "sphinx_1f", "orc_dungeon_2f"):
        assert map_id in c.maps
    for card_id in ("pirate_skeleton_card", "pasana_card", "orc_skeleton_card", "zenorc_card"):
        assert card_id in c.cards


def test_lv1_20_culvert_route_content_exists():
    c = content.load_content()
    assert "prontera_culvert_1f" in c.maps
    route = c.maps["prontera_culvert_1f"]
    assert route.level_range[0] >= 1 and route.level_range[1] <= 20
    for monster_id in ("thief_bug_egg", "thief_bug", "tarou", "thief_bug_female"):
        assert monster_id in c.monsters
        assert monster_id in route.monster_ids
        assert c.monsters[monster_id].drops
    for card_id in ("thief_bug_egg_card", "thief_bug_card", "tarou_card", "thief_bug_female_card"):
        assert card_id in c.cards
        assert c.cards[card_id].monster_id in c.monsters


def test_toy_factory_route_maps_and_cards_exist():
    c = content.load_content()
    for map_id in ("toy_factory_1f", "toy_factory_2f"):
        assert map_id in c.maps
    for card_id in ("myst_case_card", "cruiser_card", "cookie_card",
                    "chepet_card", "christmas_cookie_card"):
        assert card_id in c.cards
        assert c.cards[card_id].monster_id in c.monsters
def test_lv21_40_prejob_routes_and_cards_exist():
    c = content.load_content()
    for map_id in ("toy_factory_1f", "kobold_forest"):
        assert map_id in c.maps
    for card_id in ("cookie_card", "myst_case_card", "kobold_axe_card", "vagabond_wolf_card"):
        assert card_id in c.cards
