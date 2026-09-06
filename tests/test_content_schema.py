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
