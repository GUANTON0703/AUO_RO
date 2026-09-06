import json

import pytest

from server import content


@pytest.fixture
def tiny_data(tmp_path):
    (tmp_path / "monsters.json").write_text(json.dumps([
        {"id": "poring", "name": "波利", "level": 1, "element": "earth",
         "race": "angel", "size": "medium", "role": "glass",
         "base_exp": 2, "job_exp": 1,
         "stats": {"max_hp": 50, "max_sp": 0, "atk": 8, "matk": 0, "defense": 0,
                   "mdef": 0, "hit": 1, "flee": 6, "aspd": 100, "crit": 0},
         "drops": [{"item_id": "jellopy", "rate": 0.7}], "is_mvp": False}
    ], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "maps.json").write_text(json.dumps([
        {"id": "prontera_east_gate", "name": "東門村郊", "town": "prontera",
         "level_range": [1, 12], "monster_ids": ["poring"], "mvp_id": None,
         "unlock_base_level": 1}
    ], ensure_ascii=False), encoding="utf-8")
    for name in ["mvps", "skills", "jobs", "equipment", "cards"]:
        (tmp_path / f"{name}.json").write_text("[]", encoding="utf-8")
    (tmp_path / "items.json").write_text(json.dumps([
        {"id": "jellopy", "name": "壓縮膠", "kind": "material"}
    ], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "element_chart.json").write_text('{"table": {}}', encoding="utf-8")
    return tmp_path


def test_load_and_lookup(tiny_data):
    c = content.load_content(tiny_data)
    assert c.get_monster("poring").name == "波利"
    assert c.get_map("prontera_east_gate").town == "prontera"
    assert [m.id for m in c.monsters_on_map("prontera_east_gate")] == ["poring"]


def test_unknown_id_raises(tiny_data):
    c = content.load_content(tiny_data)
    with pytest.raises(KeyError):
        c.get_monster("nonexistent")


def test_referential_integrity_checked(tiny_data):
    # 地圖引用不存在的怪 → 載入時就爆
    (tiny_data / "maps.json").write_text(json.dumps([
        {"id": "m", "name": "x", "town": "prontera", "level_range": [1, 2],
         "monster_ids": ["ghost_monster"], "mvp_id": None, "unlock_base_level": 1}
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError):
        content.load_content(tiny_data)


def test_duplicate_id_raises(tiny_data):
    (tiny_data / "monsters.json").write_text(json.dumps([
        {"id": "poring", "name": "波利", "level": 1, "element": "earth",
         "race": "angel", "size": "medium", "role": "glass", "base_exp": 2, "job_exp": 1,
         "stats": {"max_hp": 50, "max_sp": 0, "atk": 8, "matk": 0, "defense": 0,
                   "mdef": 0, "hit": 1, "flee": 6, "aspd": 100, "crit": 0},
         "drops": [], "is_mvp": False},
        {"id": "poring", "name": "假波利", "level": 9, "element": "fire",
         "race": "animal", "size": "small", "role": "tank", "base_exp": 9, "job_exp": 4,
         "stats": {"max_hp": 500, "max_sp": 0, "atk": 20, "matk": 0, "defense": 5,
                   "mdef": 0, "hit": 9, "flee": 9, "aspd": 100, "crit": 0},
         "drops": [], "is_mvp": False},
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError, match="重複"):
        content.load_content(tiny_data)


def test_monster_and_mvp_sharing_id_raises(tiny_data):
    (tiny_data / "mvps.json").write_text(json.dumps([
        {"id": "poring", "name": "波利王", "level": 20, "element": "earth",
         "race": "angel", "size": "large", "role": "boss", "base_exp": 200, "job_exp": 100,
         "stats": {"max_hp": 9000, "max_sp": 0, "atk": 80, "matk": 0, "defense": 20,
                   "mdef": 0, "hit": 20, "flee": 20, "aspd": 110, "crit": 5},
         "drops": [], "is_mvp": True, "cooldown_hours": 8,
         "home_map_id": "prontera_east_gate"},
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError, match="共用 id"):
        content.load_content(tiny_data)


def test_skill_pointing_at_unknown_job_raises(tiny_data):
    (tiny_data / "skills.json").write_text(json.dumps([
        {"id": "phantom", "name": "幻影", "job_id": "no_such_job", "kind": "passive",
         "max_level": 5, "sp_cost": [0, 0, 0, 0, 0], "cooldown_s": 0,
         "effects": [], "idle_default": {}}
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError):
        content.load_content(tiny_data)


def test_equipment_limiting_unknown_job_raises(tiny_data):
    (tiny_data / "equipment.json").write_text(json.dumps([
        {"id": "ghost_blade", "name": "幽刃", "slot": "weapon", "rarity": "common",
         "stats": {"atk": 10}, "refinable": True, "card_slots": 1,
         "job_ids": ["no_such_job"], "required_level": 1}
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError):
        content.load_content(tiny_data)


def test_default_load_reads_repo_data_dir():
    c = content.load_content()   # 不給路徑 → 讀 repo 的 data/
    assert len(c.monsters) >= 10
