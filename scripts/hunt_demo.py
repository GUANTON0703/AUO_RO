"""養成掛機示範：Lv20 劍士在南門原野掛 6 小時（不走 HTTP，直接呼叫函式）。

跑法：uv run python scripts/hunt_demo.py
"""

import io
import random
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.content import load_content
from server.progression import CharacterSnapshot, build_player_combatant
from server.progression.levels import apply_base_exp, apply_job_exp
from server.settlement import HuntConfig, settle

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main() -> None:
    content = load_content()
    cfg = HuntConfig()

    base_level, base_exp = 20, 0
    job_level, job_exp = 15, 0
    stats = {"str": 40, "agi": 20, "vit": 25, "int": 5, "dex": 25, "luk": 10}
    learned = {"bash": 5, "sword_mastery": 5}

    snap = CharacterSnapshot(
        name="示範劍士", job_id="swordman", base_level=base_level, job_level=job_level,
        stats=stats, learned_skills=learned,
    )
    player = build_player_combatant(snap, content)
    map_def = content.get_map("prontera_south_field")
    monster_id = min(map_def.monster_ids,
                     key=lambda m: abs(content.get_monster(m).level - base_level))
    monster = content.get_monster(monster_id)

    elapsed = 6 * 3600
    rng = random.Random(hash("2026-09-06T00:00:00+00:00") & 0xFFFFFFFF)
    r = settle(player, monster, elapsed, cfg, rng,
               offline=True, pity_in={}, potion_count=0)

    new_bl, new_bexp, stat_pts = apply_base_exp(base_level, base_exp, r.base_exp)
    new_jl, new_jexp, skill_pts = apply_job_exp(job_level, job_exp, r.job_exp, "first")

    print("=" * 60)
    print(f"角色：Lv{base_level} 劍士  HP {player.max_hp} / SP {player.max_sp} / "
          f"ATK {player.atk} / HIT {player.hit} / FLEE {player.flee}")
    print(f"地圖：{map_def.name}  目標怪：{monster.name}（Lv{monster.level}）")
    print(f"掛機：離線 6 小時（效率 {cfg.offline_efficiency}）")
    print("=" * 60)
    print(f"有效時間 {r.effective_seconds / 3600:.2f}h   擊殺 {r.kills}")
    print(f"base_exp {r.base_exp}   job_exp {r.job_exp}   zeny {r.zeny}")
    print(f"掉落：{r.drops or '（無）'}")
    print(f"撤退：{r.retreated}  {r.retreat_reason}")
    print(f"收尾 HP {r.final_hp} / SP {r.final_sp}   pity {r.pity_out}")
    print("-" * 60)
    print(f"Base Level {base_level} -> {new_bl}（+{stat_pts} 屬性點），餘經驗 {new_bexp}")
    print(f"Job Level  {job_level} -> {new_jl}（+{skill_pts} 技能點），餘經驗 {new_jexp}")
    print("-" * 60)
    for e in r.events:
        print("  ", asdict(e))


if __name__ == "__main__":
    main()
