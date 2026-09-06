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
