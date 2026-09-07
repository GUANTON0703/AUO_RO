"""從 data/monsters.src.json 產生 data/monsters.json。

來源檔的條目分兩種：
- 完整條目：已帶 stats / base_exp / job_exp，原樣輸出（現有 42 隻手調怪走這條）。
- 精簡條目（帶 "gen": true）：只給 level / role / element 等欄位，
  戰鬥數值由 server.content.monster_stats.baseline() 產生，經驗用 _base_exp()。
  個別欄位可用 "overrides": {"stats": {...}, "base_exp": N} 蓋掉。

用法：
    python scripts/build_monsters.py           # 寫出 data/monsters.json
    python scripts/build_monsters.py --check    # 只比對，不寫（CI / 測試用）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.content.monster_stats import baseline   # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "monsters.src.json"
OUT = DATA / "monsters.json"

_FIELD_ORDER = ["id", "name", "level", "element", "race", "size", "role",
                "base_exp", "job_exp", "stats", "drops", "is_mvp", "lore"]
_STAT_ORDER = ["max_hp", "max_sp", "atk", "matk", "defense", "mdef",
               "hit", "flee", "aspd", "crit"]


def _base_exp(level: int, role: str) -> int:
    """對齊現有怪物的經驗曲線（Lv14 以上誤差 <5%）。"""
    exp = 0.3 * level ** 2 + 6 * level
    return max(1, round(exp * (1.27 if role in ("tank", "boss") else 1.0)))


def _expand(entry: dict) -> dict:
    level, role = entry["level"], entry["role"]
    if role not in ("glass", "normal", "tank"):
        raise ValueError(
            f"{entry['id']}: gen 條目的 role 只能是 glass/normal/tank，"
            f"boss/MVP 請寫 data/mvps.json")
    stats = baseline(level, role).model_dump()
    stats.update(entry.get("overrides", {}).get("stats", {}))
    base_exp = entry.get("overrides", {}).get("base_exp", _base_exp(level, role))
    out = {
        "id": entry["id"], "name": entry["name"], "level": level,
        "element": entry["element"], "race": entry["race"], "size": entry["size"],
        "role": role, "base_exp": base_exp, "job_exp": round(base_exp * 0.5),
        "stats": {k: stats[k] for k in _STAT_ORDER},
        "drops": entry.get("drops", []), "is_mvp": entry.get("is_mvp", False),
        "lore": entry.get("lore", ""),
    }
    return out


def _canonical(entry: dict) -> dict:
    if entry.get("gen"):
        return _expand(entry)
    ordered = {k: entry[k] for k in _FIELD_ORDER if k in entry}
    ordered["stats"] = {k: entry["stats"][k] for k in _STAT_ORDER}
    return ordered


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _render(m: dict) -> str:
    """一隻怪一段：stats 與每個 drop 各壓成一行，其餘照 2 空格縮排。"""
    lines = ["  {"]
    for key in _FIELD_ORDER:
        if key not in m:
            continue
        if key == "stats":
            lines.append(f'    "stats": {_dumps(m["stats"])},')
        elif key == "drops":
            drops = m["drops"]
            if not drops:
                lines.append('    "drops": [],')
            else:
                lines.append('    "drops": [')
                for i, d in enumerate(drops):
                    tail = "," if i < len(drops) - 1 else ""
                    lines.append(f"      {_dumps(d)}{tail}")
                lines.append("    ],")
        else:
            lines.append(f'    "{key}": {_dumps(m[key])},')
    lines[-1] = lines[-1].rstrip(",")   # 最後一個欄位不留逗號
    lines.append("  }")
    return "\n".join(lines)


def build() -> str:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    monsters = [_canonical(e) for e in src]
    body = ",\n".join(_render(m) for m in monsters)
    return f"[\n{body}\n]\n"


def main() -> int:
    rendered = build()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8")
        if current != rendered:
            print("data/monsters.json 與 monsters.src.json 不同步，請跑 build_monsters.py")
            return 1
        print("monsters.json 同步 OK")
        return 0
    OUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"寫出 {OUT.relative_to(DATA.parent)}（{rendered.count(chr(10))} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
