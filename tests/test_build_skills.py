"""data/skills.json 必須是 scripts/build_skills.py 從 skills.src.json 產出的結果。"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "build_skills", _ROOT / "scripts" / "build_skills.py")
build_skills = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_skills)


def test_skills_json_is_in_sync_with_source():
    rendered = build_skills.render()
    committed = (_ROOT / "data" / "skills.json").read_text(encoding="utf-8")
    assert rendered == committed, "跑 python scripts/build_skills.py 重新產生 skills.json"


def test_check_mode_passes_on_committed_data():
    assert build_skills.main(["--check"]) == 0
