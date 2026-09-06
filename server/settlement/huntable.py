import random

from server.combat.combatant import Combatant
from server.settlement.profile import estimate_fight_profile
from server.settlement.strategy import HuntStrategy

# 自動選怪時，一場打超過這麼多回合就不列入（太拖、耗補品、體感差）
_MAX_AUTO_ROUNDS = 12.0
# 一場平均掉血超過血量這個比例，即使勝率看起來夠也不列入（連輸幾場會死）
_MAX_DMG_FRAC = 0.55
# 模擬用固定亂數種子 + 較多樣本，讓「能不能打」的判斷穩定、不會每次輪詢跳來跳去
_EVAL_SEED = 20260907
_EVAL_SAMPLES = 30


def _profiles(player: Combatant, map_def, content) -> dict:
    """每隻怪跑一次模擬，回 {mid: FightProfile}。用固定種子確保穩定。"""
    return {
        mid: estimate_fight_profile(player, content.get_monster(mid),
                                    random.Random(_EVAL_SEED), samples=_EVAL_SAMPLES)
        for mid in map_def.monster_ids
    }


def _ok(profile, player: Combatant, threshold: float) -> bool:
    return (profile.win_rate >= threshold
            and profile.avg_rounds <= _MAX_AUTO_ROUNDS
            and profile.avg_damage_taken <= player.max_hp * _MAX_DMG_FRAC)


def win_rate(player: Combatant, monster, rng: random.Random, samples: int = 12) -> float:
    return estimate_fight_profile(player, monster, rng, samples=samples).win_rate


def huntable_monsters(player: Combatant, map_def, strategy: HuntStrategy, content,
                      rng: random.Random, threshold: float) -> list[str]:
    """回傳這次掛機該輪替的怪 id 清單。

    玩家有手動指定（strategy.include_monsters）就完全照指定，不套勝率過濾、
    也不套 exclude。沒指定則從未被 exclude、又打得穩的怪裡挑。
    """
    if strategy.include_monsters:
        return [mid for mid in map_def.monster_ids
                if mid in strategy.include_monsters]
    prof = _profiles(player, map_def, content)
    return [
        mid for mid in map_def.monster_ids
        if mid not in strategy.exclude_monsters and _ok(prof[mid], player, threshold)
    ]


def pick_start_monster(player: Combatant, map_def, strategy: HuntStrategy, content,
                       rng: random.Random, threshold: float) -> str | None:
    """開始掛機時的起始怪。自動模式挑「打得穩之中經驗效率最高」的
    （經驗 / 回合數，也就是升級最快）。全都打不穩回 None。
    手動模式回指定清單第一隻。"""
    if strategy.include_monsters:
        cands = huntable_monsters(player, map_def, strategy, content, rng, threshold)
        return cands[0] if cands else None
    prof = _profiles(player, map_def, content)
    winnable = [
        mid for mid in map_def.monster_ids
        if mid not in strategy.exclude_monsters and _ok(prof[mid], player, threshold)
    ]
    if not winnable:
        return None
    return max(
        winnable,
        key=lambda mid: content.get_monster(mid).base_exp / max(1.0, prof[mid].avg_rounds),
    )
