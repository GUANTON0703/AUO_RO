"""戰鬥引擎示範腳本：肉眼檢查平衡感。

跑法：uv run python scripts/combat_demo.py
"""

import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.combat import Combatant, ResolvedSkill, simulate_fight, simulate_grind
from server.content import load_content

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _fmt_event(e) -> str:
    if e.kind == "attack":
        if not e.hit:
            return f"  {e.actor} 攻擊 {e.target} → MISS"
        tag = " 暴擊!" if e.crit else ""
        return f"  {e.actor} 攻擊 {e.target} → {e.damage} 傷害{tag}"
    if e.kind == "skill":
        return f"  {e.actor} 對 {e.target} 施放【{e.skill_name}】→ {e.damage} 傷害"
    if e.kind == "heal":
        return f"  {e.actor} 回復 {e.amount} HP"
    if e.kind == "kill":
        return f"  {e.actor} 擊倒了 {e.target}"
    if e.kind == "status_applied":
        return f"  {e.target} 進入狀態 {e.status}（{e.duration} 回合）"
    if e.kind == "status_expired":
        return f"  {e.target} 的 {e.status} 結束"
    return f"  {e.kind}"


def _make_swordman(content) -> Combatant:
    bash_def = content.skills["bash"]
    bash = ResolvedSkill(
        skill_id="bash", name=bash_def.name, level=3, kind="active",
        sp_cost=bash_def.sp_cost[2], cooldown_rounds=0, effects=bash_def.effects,
        trigger="every_turn", priority=1,
    )
    return Combatant(
        name="示範劍士", max_hp=600, max_sp=40, atk=90, matk=5, defense=8,
        mdef=3, hit=45, flee=35, aspd=130, crit=5, skills=[bash],
    )


def main() -> None:
    content = load_content()

    print("=" * 60)
    print("ROtxt 戰鬥引擎示範（seed=42）")
    print("=" * 60)

    for mid in ("green_cotton_worm", "wolf", "curly_boar_king"):
        monster = content.get_monster(mid)
        hero = _make_swordman(content)
        foe = Combatant.from_monster(monster)
        rng = random.Random(42)
        result = simulate_fight(hero, foe, rng)

        print()
        print(f"--- {hero.name} (Lv15) vs {monster.name} (Lv{monster.level}, "
              f"HP {monster.stats.max_hp}) ---")
        for e in result.events[:15]:
            print(_fmt_event(e))
        if len(result.events) > 15:
            print(f"  ... 省略 {len(result.events) - 15} 條事件 ...")
        print(f"  結果：{result.outcome} / 勝者={result.winner} / "
              f"回合數={result.rounds} / 勝方HP={result.winner_hp} / "
              f"敗方HP={result.loser_hp}")

    print()
    print("=" * 60)
    print("掛機模擬：示範劍士連打綠棉蟲 30 場（血/魔跨場不重置）")
    print("=" * 60)
    hero = _make_swordman(content)
    worm = content.get_monster("green_cotton_worm")
    grind = simulate_grind(hero, worm, n_fights=30, rng=random.Random(42))
    print(f"  擊殺數        ：{grind.kills} / {grind.fights_attempted}")
    print(f"  base_exp     ：{grind.base_exp}")
    print(f"  job_exp      ：{grind.job_exp}")
    print(f"  總回合數      ：{grind.total_rounds}")
    print(f"  累計受到傷害  ：{grind.damage_taken}")
    print(f"  玩家陣亡      ：{grind.player_defeated}")
    print(f"  結束時劍士HP  ：{hero.hp} / {hero.max_hp}")


if __name__ == "__main__":
    main()
