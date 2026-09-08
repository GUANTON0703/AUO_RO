"""從 data/skills.src.json 產生 data/skills.json。

來源檔是一行一技能的緊湊 JSON 陣列（方便逐技能 review 與小 diff）。
輸出是 2-space 縮排的展開格式，與 app 讀取的 data/skills.json 完全一致。

用法：
    python scripts/build_skills.py           # 寫出 data/skills.json
    python scripts/build_skills.py --check    # 只比對，不寫（CI / 測試用）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "skills.src.json"
OUT = DATA / "skills.json"


def render() -> str:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("data/skills.json 與 skills.src.json 不同步，請跑 python scripts/build_skills.py")
            return 1
        print("OK")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"寫出 {OUT.name}（{len(json.loads(text))} 個技能）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
