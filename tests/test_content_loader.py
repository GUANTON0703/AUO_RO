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


def test_default_load_reads_repo_data_dir():
    c = content.load_content()   # 不給路徑 → 讀 repo 的 data/
    assert len(c.monsters) >= 10
