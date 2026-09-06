import random

from server.combat.combatant import Combatant
from server.settlement.profile import estimate_fight_profile
from server.settlement.strategy import HuntStrategy


def win_rate(player: Combatant, monster, rng: random.Random, samples: int = 12) -> float:
    return estimate_fight_profile(player, monster, rng, samples=samples).win_rate


def huntable_monsters(player: Combatant, map_def, strategy: HuntStrategy, content,
                      rng: random.Random, threshold: float) -> list[str]:
    """回傳這次掛機該輪替的怪 id 清單。

    玩家有手動指定（strategy.include_monsters）就完全照指定，不套勝率過濾、
    也不套 exclude。沒指定則從未被 exclude 的怪裡，只留勝率 >= threshold 的。
    """
    if strategy.include_monsters:
        return [mid for mid in map_def.monster_ids
                if mid in strategy.include_monsters]
    return [
        mid for mid in map_def.monster_ids
        if mid not in strategy.exclude_monsters
        and win_rate(player, content.get_monster(mid), rng) >= threshold
    ]


def pick_start_monster(player: Combatant, map_def, strategy: HuntStrategy, content,
                       rng: random.Random, threshold: float) -> str | None:
    """開始掛機時的起始怪。自動模式挑「打得贏之中經驗最高」的；
    全都打不贏回 None（呼叫端據此擋下或提示）。手動模式回指定清單第一隻。"""
    candidates = huntable_monsters(player, map_def, strategy, content, rng, threshold)
    if strategy.include_monsters:
        return candidates[0] if candidates else None
    if not candidates:
        return None
    return max(candidates, key=lambda mid: content.get_monster(mid).base_exp)
