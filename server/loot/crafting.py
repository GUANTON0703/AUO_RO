import random

CRAFT_LEVEL_CAP = 10
GREAT_SUCCESS_PCT = 8   # 大成功機率，跟配方成功率分開判定
_EXP_GAIN = {"fail": 3, "success": 8, "great": 16}


def craft_exp_for_next(level: int) -> int:
    return 40 * level


MASTERY_PER_ATTEMPT = 5     # 每做幾次這張配方加一次熟練度
MASTERY_CAP_PCT = 15        # 熟練度封頂加成（%）


def mastery_bonus_pct(attempts: int) -> int:
    """這張配方做過幾次帶來的額外成功率，跟角色製作等級的加成分開算、疊加。"""
    return min(MASTERY_CAP_PCT, attempts // MASTERY_PER_ATTEMPT)


def success_rate(recipe, craft_level: int, mastery_attempts: int = 0) -> int:
    """製作等級每超過配方門檻一級 +5%，反過來低於門檻也會扣；
    這張配方做得越多熟練度加成越高（跟等級加成分開算，封頂 95%、下限 5%）。"""
    pct = recipe.base_success_pct + (craft_level - recipe.required_craft_level) * 5 \
        + mastery_bonus_pct(mastery_attempts)
    return max(5, min(95, pct))


def apply_craft_exp(level: int, exp: int, gained: int) -> tuple[int, int]:
    exp += gained
    while level < CRAFT_LEVEL_CAP and exp >= craft_exp_for_next(level):
        exp -= craft_exp_for_next(level)
        level += 1
    if level >= CRAFT_LEVEL_CAP:
        exp = 0
    return level, exp


def attempt_craft(recipe, craft_level: int, mastery_attempts: int,
                  rng: random.Random) -> tuple[bool, bool, int]:
    """回傳 (success, great_success, exp_gained)。材料不管成功失敗都會在外層扣掉。"""
    if rng.random() * 100 < success_rate(recipe, craft_level, mastery_attempts):
        great = rng.random() * 100 < GREAT_SUCCESS_PCT
        return True, great, _EXP_GAIN["great" if great else "success"]
    return False, False, _EXP_GAIN["fail"]
