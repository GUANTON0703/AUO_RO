from scripts.check_content import check, check_content


def test_current_content_data_passes():
    assert check() == []


def test_catches_card_not_in_monster_drops():
    eq = [{"id": "hat", "slot": "head", "card_slots": 1, "stats": {"def": 2}}]
    cards = [{"id": "x_card", "slot": "head", "drop_rate": 0.01,
              "monster_id": "poring", "effects": [{"type": "flat_stat", "stat": "atk", "amount": 1}]}]
    mons = [{"id": "poring", "drops": []}]
    errs = check_content(eq, cards, mons, [])
    assert any("打不到" in e for e in errs)


def test_catches_bad_size_damage_effect():
    cards = [{"id": "y_card", "slot": "weapon", "drop_rate": 0.01, "monster_id": "poring",
              "effects": [{"type": "size_damage", "size": "huge", "pct": 15}]}]
    mons = [{"id": "poring", "drops": [{"item_id": "y_card"}]}]
    errs = check_content([], cards, mons, [])
    assert any("size" in e for e in errs)
