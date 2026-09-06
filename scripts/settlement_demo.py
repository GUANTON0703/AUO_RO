"""掛機結算器示範腳本：肉眼檢查 8 小時掛機的收成合不合理。

跑法：uv run python scripts/settlement_demo.py
"""

import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.combat import Combatant, ResolvedSkill
from server.content import load_content
from server.settlement import HuntConfig, settle

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _hero(content) -> Combatant:
    bash_def = content.skills["bash"]
    bash = ResolvedSkill(
        skill_id="bash", name=bash_def.name, level=3, kind="active",
        sp_cost=bash_def.sp_cost[2], cooldown_rounds=0, effects=bash_def.effects,
        trigger="every_turn", priority=3,
    )
    return Combatant(
        name="示範英雄", max_hp=3200, max_sp=180, atk=240, matk=12, defense=28,
        mdef=14, hit=145, flee=115, aspd=158, crit=15, skills=[bash],
    )


def _fmt_drops(drops: dict) -> str:
    if not drops:
        return "（無）"
    return "、".join(f"{k}×{v}" for k, v in sorted(drops.items()))


def _fmt_events(events: list) -> str:
    lines = []
    for e in events:
        if e.kind == "kill_batch":
            lines.append(f"    擊殺批次 {e.monster_name}×{e.count}"
                         f"（base {e.base_exp} / job {e.job_exp} / zeny {e.zeny}）")
        elif e.kind == "rare_drop":
            lines.append(f"    稀有掉落 {e.item_name}×{e.qty}")
        elif e.kind == "potion_used":
            lines.append(f"    補品消耗 {e.item_id}×{e.count}（剩 {e.remaining}）")
        elif e.kind == "retreat":
            lines.append(f"    撤退：{e.reason}（撐了 {e.seconds_survived / 3600:.2f} 小時）")
    return "\n".join(lines) if lines else "    （無事件）"


def _report(title: str, r) -> None:
    print(f"  {title}")
    print(f"    有效時間 {r.effective_seconds / 3600:.2f}h / 實際 {r.real_elapsed_seconds / 3600:.2f}h"
          f"    擊殺 {r.kills}")
    print(f"    base_exp {r.base_exp}    job_exp {r.job_exp}    zeny {r.zeny}")
    print(f"    掉落：{_fmt_drops(r.drops)}")
    print(f"    補品用量 {r.potions_used}    撤退 {r.retreated}"
          f"{('（' + r.retreat_reason + '）') if r.retreated else ''}")
    print(f"    收尾 HP {r.final_hp} / SP {r.final_sp}    pity {r.pity_out}")
    print(_fmt_events(r.events))
    print()


def main() -> None:
    content = load_content()
    cfg = HuntConfig()

    maps = [
        ("波利草原（prontera_west_plain）", "poring"),
        ("南門原野（prontera_south_field）", "raccoon"),
        ("北方密林（prontera_north_forest）", "wolf"),
    ]

    print("=" * 68)
    print("ROtxt 掛機結算器示範（seed=2026）")
    print(f"英雄：HP 3200 / SP 180 / ATK 240 / 帶 3 級 Bash")
    print(f"設定：離線效率 {cfg.offline_efficiency} / 上限 {cfg.offline_cap_hours}h"
          f" / 卡片保底 {cfg.card_pity_threshold}")
    print("=" * 68)

    for label, mid in maps:
        monster = content.get_monster(mid)
        print(f"\n■ {label}　目標怪：{monster.name}（Lv{monster.level}, "
              f"base_exp {monster.base_exp}）")

        r_off = settle(_hero(content), monster, elapsed_seconds=8 * 3600, cfg=cfg,
                       rng=random.Random(2026), offline=True, pity_in={},
                       potion_item_id="red_potion", potion_heal=45,
                       potion_count=2000)
        _report("離線掛機 8 小時", r_off)

        r_on = settle(_hero(content), monster, elapsed_seconds=5 * 60, cfg=cfg,
                      rng=random.Random(2026), offline=False, pity_in={},
                      potion_item_id="red_potion", potion_heal=45,
                      potion_count=2000)
        _report("在線掛機 5 分鐘（逐場）", r_on)

        if r_on.kills:
            ratio = (r_off.kills / (8 * 3600)) / (r_on.kills / (5 * 60))
            print(f"    每秒擊殺比（離線/在線）≈ {ratio:.2f}"
                  f"（期望 ≈ {cfg.offline_efficiency}）\n")


if __name__ == "__main__":
    main()
