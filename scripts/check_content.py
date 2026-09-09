"""驗證 data/equipment.json 與 data/cards.json 的格式，補 server 完整性檢查沒管的部分。

用法：
    python scripts/check_content.py     # 全過印 OK exit 0，有錯印清單 exit 1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

CARD_EFFECT_TYPES = {
    "flat_stat", "percent_stat", "element_resist", "race_damage",
    "size_damage", "weapon_element", "on_hit_proc",   # on_hit_proc 目前戰鬥不套用（保留）
}
ELEMENTS = {"neutral", "water", "earth", "fire", "wind",
            "poison", "holy", "shadow", "ghost", "undead"}
RACES = {"animal", "plant", "insect", "demon", "undead",
         "demihuman", "angel", "dragon", "formless", "fish"}
SIZES = {"small", "medium", "large"}
GEAR_SLOTS = {"weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"}
# 裝備與卡片 stats 一律用 defense/mdef（對齊戰鬥引擎的 effective_* key）
_COMMON = {"atk", "matk", "hit", "flee", "crit", "aspd",
           "max_hp", "max_sp", "str", "agi", "vit", "int", "dex", "luk"}
EQUIP_STAT_KEYS = _COMMON | {"defense", "mdef"}
CARD_STAT_KEYS = _COMMON | {"defense", "mdef"}


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_content(equipment: list, cards: list, monsters: list, mvps: list) -> list[str]:
    errors: list[str] = []
    eq_by_id = {}
    for e in equipment:
        if e["id"] in eq_by_id:
            errors.append(f"裝備 id 重複：{e['id']}")
        eq_by_id[e["id"]] = e
        if e.get("slot") not in GEAR_SLOTS:
            errors.append(f"裝備 {e['id']}：slot {e.get('slot')!r} 不合法")
        cs = e.get("card_slots", 0)
        if not (_is_int(cs) and 0 <= cs <= 4):
            errors.append(f"裝備 {e['id']}：card_slots 必須 0~4，目前 {cs!r}")
        for k in e.get("stats", {}):
            if k not in EQUIP_STAT_KEYS:
                errors.append(f"裝備 {e['id']}：未知數值欄位 {k!r}")
        if e.get("required_level", 1) < 1:
            errors.append(f"裝備 {e['id']}：required_level 必須 >= 1")

    drops_by_monster = {m["id"]: {d["item_id"] for d in m.get("drops", [])}
                        for m in list(monsters) + list(mvps)}
    all_monster_ids = set(drops_by_monster)

    seen = set()
    for c in cards:
        cid = c["id"]
        if cid in seen:
            errors.append(f"卡片 id 重複：{cid}")
        seen.add(cid)
        if c.get("slot") not in GEAR_SLOTS:
            errors.append(f"卡片 {cid}：slot {c.get('slot')!r} 不合法")
        dr = c.get("drop_rate", 0)
        if not (isinstance(dr, (int, float)) and 0 < dr <= 1):
            errors.append(f"卡片 {cid}：drop_rate 必須是 0~1，目前 {dr!r}")
        mid = c.get("monster_id")
        if mid not in all_monster_ids:
            errors.append(f"卡片 {cid}：monster_id {mid!r} 不存在")
        elif cid not in drops_by_monster.get(mid, set()):
            errors.append(f"卡片 {cid}：對應怪 {mid} 的掉落表沒有列這張卡（打不到）")
        for i, eff in enumerate(c.get("effects", []), start=1):
            t = eff.get("type")
            if t not in CARD_EFFECT_TYPES:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：type {t!r} 不合法")
            if t in ("flat_stat", "percent_stat") and eff.get("stat") not in CARD_STAT_KEYS:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：stat {eff.get('stat')!r} 未知")
            if t == "element_resist" and eff.get("element") not in ELEMENTS:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：element {eff.get('element')!r} 不合法")
            if t == "weapon_element" and eff.get("element") not in ELEMENTS:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：element {eff.get('element')!r} 不合法")
            if t == "race_damage" and eff.get("race") not in RACES:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：race {eff.get('race')!r} 不合法")
            if t == "size_damage" and eff.get("size") not in SIZES:
                errors.append(f"卡片 {cid} 第 {i} 個 effect：size {eff.get('size')!r} 不合法")
    return errors


def check() -> list[str]:
    load = lambda f: json.loads((DATA / f).read_text(encoding="utf-8"))
    return check_content(load("equipment.json"), load("cards.json"),
                         load("monsters.json"), load("mvps.json"))


def main() -> int:
    errs = check()
    if errs:
        for e in errs:
            print(e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
