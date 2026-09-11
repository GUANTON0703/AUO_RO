import random

CRAFT_LEVEL_CAP = 10
GREAT_SUCCESS_PCT = 8   # 大成功機率，跟配方成功率分開判定
_EXP_GAIN = {"fail": 3, "success": 8, "great": 16}


def craft_exp_for_next(level: int) -> int:
    return 40 * level


def success_rate(recipe, craft_level: int) -> int:
    """製作等級每超過配方門檻一級 +5%，反過來低於門檻也會扣，封頂 95%、下限 5%。"""
    pct = recipe.base_success_pct + (craft_level - recipe.required_craft_level) * 5
    return max(5, min(95, pct))


def apply_craft_exp(level: int, exp: int, gained: int) -> tuple[int, int]:
    exp += gained
    while level < CRAFT_LEVEL_CAP and exp >= craft_exp_for_next(level):
        exp -= craft_exp_for_next(level)
        level += 1
    if level >= CRAFT_LEVEL_CAP:
        exp = 0
    return level, exp


def attempt_craft(recipe, craft_level: int, rng: random.Random) -> tuple[bool, bool, int]:
    """回傳 (success, great_success, exp_gained)。材料不管成功失敗都會在外層扣掉。"""
    if rng.random() * 100 < success_rate(recipe, craft_level):
        great = rng.random() * 100 < GREAT_SUCCESS_PCT
        return True, great, _EXP_GAIN["great" if great else "success"]
    return False, False, _EXP_GAIN["fail"]
