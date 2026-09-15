"""驗證 data/skills.json 的格式，擋掉手動加技能時的錯誤。

純檢查器，不寫任何檔案。蒐集所有錯誤後一次印出。

用法：
    python scripts/check_skills.py     # 全過印 OK exit 0，有錯印清單 exit 1

測試可 import：
    from scripts.check_skills import check          # 讀檔 + 檢查
    from scripts.check_skills import check_skills    # 純邏輯，餵 list[dict]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA = Path(__file__).resolve().parent.parent / "data"

EFFECT_TYPES = {
    "physical_hit", "magic_hit", "aoe", "heal_hp", "heal_sp",
    "buff", "debuff", "passive_stat", "proc",
    "shop_discount_pct", "shop_overcharge_pct",
}
ELEMENTS = {
    "neutral", "water", "earth", "fire", "wind",
    "poison", "holy", "shadow", "ghost", "undead",
}
TRIGGERS = {
    "passive", "every_turn", "cooldown_ready",
    "sp_available", "hp_below_50", "hp_below_30",
}
LEVEL_LIST_FIELDS = ["power_pct", "matk_pct", "amount", "pct", "chance_pct", "hits"]


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_skills(skills: list[dict], jobs: list[dict]) -> list[str]:
    """對已解析的 skills / jobs 資料跑格式檢查，回傳中文錯誤字串清單。"""
    errors: list[str] = []

    job_by_id = {j.get("id"): j for j in jobs}
    skill_by_id: dict[str, dict] = {}

    def ancestry(job_id) -> set:
        seen: set = set()
        cur = job_by_id.get(job_id)
        while cur and cur.get("id") not in seen:
            seen.add(cur.get("id"))
            pid = cur.get("parent_id")
            cur = job_by_id.get(pid) if pid else None
        return seen

    # 1. 技能 id 重複
    seen_ids: set = set()
    for s in skills:
        sid = s.get("id")
        if sid in seen_ids:
            errors.append(f"技能 id 重複：{sid}")
        seen_ids.add(sid)
        skill_by_id[sid] = s

    for s in skills:
        sid = s.get("id", "<無 id>")
        max_level = s.get("max_level")
        kind = s.get("kind")

        # 2. max_level 是 1~10 的整數
        if not (_is_int(max_level) and 1 <= max_level <= 10):
            errors.append(f"技能 {sid}：max_level 必須是 1~10 的整數，目前為 {max_level!r}")

        # 3. kind
        if kind not in ("active", "passive"):
            errors.append(f"技能 {sid}：kind 只能是 active 或 passive，目前為 {kind!r}")

        # 4. job_id 存在
        job_id = s.get("job_id")
        if job_id not in job_by_id:
            errors.append(f"技能 {sid}：job_id {job_id!r} 不存在於 jobs.json")

        # 5. sp_cost
        sp_cost = s.get("sp_cost") or []
        if not isinstance(sp_cost, list):
            errors.append(f"技能 {sid}：sp_cost 必須是陣列，目前為 {sp_cost!r}")
            sp_cost = []
        elif any(not _is_int(x) for x in sp_cost):
            errors.append(f"技能 {sid}：sp_cost 內容必須是整數")
        if sp_cost and _is_int(max_level) and len(sp_cost) != max_level:
            errors.append(
                f"技能 {sid}：sp_cost 長度 {len(sp_cost)} 不等於 max_level {max_level}")
        if kind == "passive" and any(_is_int(x) and x != 0 for x in sp_cost):
            errors.append(f"技能 {sid}：passive 技能的 sp_cost 必須全 0 或空陣列")

        # 6~8. effects
        effects = s.get("effects") or []
        if not isinstance(effects, list) or any(not isinstance(e, dict) for e in effects):
            errors.append(f"技能 {sid}：effects 必須是 dict 陣列")
            effects = []
        for i, eff in enumerate(effects, start=1):
            etype = eff.get("type")
            if etype not in EFFECT_TYPES:
                errors.append(f"技能 {sid} 第 {i} 個 effect：type {etype!r} 不合法")
            for field in LEVEL_LIST_FIELDS:
                v = eff.get(field)
                if isinstance(v, list) and _is_int(max_level) and len(v) != max_level:
                    errors.append(
                        f"技能 {sid} 第 {i} 個 effect：{field} 長度 {len(v)} "
                        f"不等於 max_level {max_level}")
            stats = eff.get("stats")
            if isinstance(stats, dict):
                for stat_name, seq in stats.items():
                    if isinstance(seq, list) and _is_int(max_level) and len(seq) != max_level:
                        errors.append(
                            f"技能 {sid} 第 {i} 個 effect：stats.{stat_name} 長度 "
                            f"{len(seq)} 不等於 max_level {max_level}")
            elem = eff.get("element")
            if elem is not None and elem not in ELEMENTS:
                errors.append(f"技能 {sid} 第 {i} 個 effect：element {elem!r} 不合法")

        # 9. requires
        requires = s.get("requires") or {}
        if not isinstance(requires, dict):
            errors.append(f"技能 {sid}：requires 必須是物件")
            requires = {}
        for req_id, req_lv in requires.items():
            if req_id not in skill_by_id:
                errors.append(f"技能 {sid}：前置技能 {req_id} 不存在")
                continue
            dep = skill_by_id[req_id]
            dep_max = dep.get("max_level")
            if not _is_int(req_lv) or req_lv < 1 or (_is_int(dep_max) and req_lv > dep_max):
                errors.append(
                    f"技能 {sid}：前置 {req_id} 的需求等級 {req_lv!r} 不合法"
                    f"（須是 1~{dep_max} 的整數）")
            if dep.get("job_id") not in ancestry(job_id):
                errors.append(
                    f"技能 {sid}：前置技能 {req_id}（職業 {dep.get('job_id')}）"
                    f"不在本職或前職鏈上")

        # 10. idle_default.trigger
        idle = s.get("idle_default") or {}
        if not isinstance(idle, dict):
            errors.append(f"技能 {sid}：idle_default 必須是物件")
            idle = {}
        trigger = idle.get("trigger")
        if trigger is not None:
            if trigger not in TRIGGERS:
                errors.append(f"技能 {sid}：idle_default.trigger {trigger!r} 不合法")
            elif kind == "passive" and trigger != "passive":
                errors.append(
                    f"技能 {sid}：passive 技能的 idle_default.trigger 必須是 passive，"
                    f"目前為 {trigger!r}")

    # 11. job.skill_ids 必須剛好等於該 job 的技能集合
    for j in jobs:
        jid = j.get("id")
        declared = set(j.get("skill_ids") or [])
        actual = {s.get("id") for s in skills if s.get("job_id") == jid}
        for sid in sorted(declared - actual):
            errors.append(
                f"職業 {jid}：skill_ids 列了 {sid}，但 skills.json 沒有 job_id={jid} 的對應技能")
        for sid in sorted(actual - declared):
            errors.append(
                f"職業 {jid}：skills.json 有 {sid}（job_id={jid}）但 job 的 skill_ids 沒列")

    return errors


def check() -> list[str]:
    """讀 data/skills.json 與 data/jobs.json 跑檢查。"""
    skills = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))
    jobs = json.loads((DATA / "jobs.json").read_text(encoding="utf-8"))
    return check_skills(skills, jobs)


def main() -> int:
    errors = check()
    if errors:
        for e in errors:
            print(e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
