from shared.content import Element, Race, Size, Stat


def test_element_has_16_ro_elements():
    expected = {
        "neutral", "water", "earth", "fire", "wind", "poison",
        "holy", "shadow", "ghost", "undead",
    }
    assert expected <= {e.value for e in Element}


def test_race_covers_ludens_families():
    # ludens 用詞：動物系/植物系/昆蟲系/惡魔系/不死系/人形系/天使系(聖靈系)/龍族/無形/魚貝
    families = {
        "animal", "plant", "insect", "demon", "undead",
        "demihuman", "angel", "dragon", "formless", "fish",
    }
    assert families <= {r.value for r in Race}


def test_size_is_small_medium_large():
    assert {s.value for s in Size} >= {"small", "medium", "large"}


def test_stat_enum_has_six_primary():
    assert {s.value for s in Stat} == {"str", "agi", "vit", "int", "dex", "luk"}


def test_combat_stats_round_trip():
    from shared.content import CombatStats

    cs = CombatStats(max_hp=50, max_sp=0, atk=8, matk=0, defense=0, mdef=0,
                     hit=1, flee=1, aspd=100, crit=0)
    assert CombatStats.model_validate(cs.model_dump()) == cs


def test_monster_def_requires_core_fields():
    from shared.content import MonsterDef, CombatStats, Element, Race, Size

    m = MonsterDef(
        id="poring", name="波利", level=1, element=Element.EARTH,
        race=Race.ANGEL, size=Size.MEDIUM, role="glass",
        base_exp=2, job_exp=1,
        stats=CombatStats(max_hp=50, max_sp=0, atk=8, matk=0, defense=0,
                          mdef=0, hit=1, flee=1, aspd=100, crit=0),
        drops=[], is_mvp=False,
    )
    assert m.id == "poring"
    assert MonsterDef.model_validate(m.model_dump()) == m


def test_drop_entry_rate_is_fraction():
    from shared.content import DropEntry
    import pytest

    DropEntry(item_id="jellopy", rate=0.5)
    with pytest.raises(Exception):
        DropEntry(item_id="jellopy", rate=1.5)


def test_map_def():
    from shared.content import MapDef

    m = MapDef(id="prontera_east_gate", name="普隆德拉野外-東門村郊",
               town="prontera", level_range=[1, 12],
               monster_ids=["green_cotton_worm", "mad_bunny"],
               mvp_id=None, unlock_base_level=1)
    assert m.town == "prontera"


def test_skill_def_effects_are_structured():
    from shared.content import SkillDef

    s = SkillDef(
        id="bash", name="爆裂波動", job_id="swordman", kind="active",
        max_level=10, sp_cost=[8, 8, 9, 9, 10], cooldown_s=0,
        effects=[{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
        idle_default={"enabled": True, "trigger": "every_turn", "priority": 1},
    )
    assert s.kind == "active"


def test_card_effect_flat_stat_and_proc():
    from shared.content import CardDef

    c = CardDef(
        id="poring_card", name="波利卡片", monster_id="poring",
        slot="armor", drop_rate=0.001,
        effects=[
            {"type": "flat_stat", "stat": "max_hp", "amount": 100},
            {"type": "on_kill_proc", "chance_pct": 100, "effect": "heal_hp", "amount": 5},
        ],
    )
    assert c.slot == "armor"


def test_equipment_slot_and_refine():
    from shared.content import EquipmentDef

    e = EquipmentDef(
        id="knife", name="小刀", slot="weapon", rarity="common",
        stats={"atk": 17}, refinable=True, card_slots=1,
        job_ids=["novice", "swordman", "thief"], required_level=1,
    )
    assert e.refinable is True


def test_element_chart_multiplier_lookup():
    from shared.content import ElementChart

    chart = ElementChart(table={"fire": {"earth": 1.5, "water": 0.5, "fire": 0.25}})
    assert chart.multiplier("fire", "earth") == 1.5
    assert chart.multiplier("fire", "wind") == 1.0   # 未列 = 中性
