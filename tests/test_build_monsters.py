"""data/monsters.json 必須是 scripts/build_monsters.py 從 monsters.src.json 產出的結果。"""
import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "build_monsters", _ROOT / "scripts" / "build_monsters.py")
build_monsters = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_monsters)


def test_monsters_json_is_in_sync_with_source():
    rendered = build_monsters.build()
    committed = (_ROOT / "data" / "monsters.json").read_text(encoding="utf-8")
    assert rendered == committed, "跑 python scripts/build_monsters.py 重新產生 monsters.json"


def test_generated_entry_has_all_stat_keys():
    entry = build_monsters._expand({
        "id": "x", "name": "x", "level": 20, "element": "neutral",
        "race": "formless", "size": "medium", "role": "normal",
    })
    assert set(entry["stats"]) == set(build_monsters._STAT_ORDER)
    assert entry["job_exp"] == round(entry["base_exp"] * 0.5)


def test_overrides_win_over_formula():
    entry = build_monsters._expand({
        "id": "pupa", "name": "蟲蛹", "level": 2, "element": "poison",
        "race": "insect", "size": "small", "role": "tank",
        "overrides": {"stats": {"flee": 1, "atk": 0}, "base_exp": 2},
    })
    assert entry["stats"]["flee"] == 1 and entry["stats"]["atk"] == 0
    assert entry["base_exp"] == 2 and entry["job_exp"] == 1


def test_generated_classic_batch_one_monsters_keep_required_drops():
    source = json.loads((build_monsters.DATA / "monsters.src.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in source}
    for monster_id in ("pirate_skeleton", "pasana", "orc_skeleton"):
        assert entries[monster_id]["gen"] is True
        assert entries[monster_id]["drops"]


def test_generated_toy_factory_monsters_keep_required_drops():
    source = json.loads((build_monsters.DATA / "monsters.src.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in source}
    for monster_id in ("myst_case", "cruiser", "cookie", "chepet", "christmas_cookie"):
        assert entries[monster_id]["gen"] is True
        drop_ids = {d["item_id"] for d in entries[monster_id]["drops"]}
        assert drop_ids, monster_id
        assert f"{monster_id}_card" in drop_ids
