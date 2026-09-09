import random

REFINE_CAP = 10
_RATE = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.6, 5: 0.4,
         6: 0.4, 7: 0.25, 8: 0.2, 9: 0.1}
_ARMOR_SLOTS = {"armor", "shoes", "head", "garment", "offhand", "accessory"}


def success_rate(current_refine: int) -> float:
    if current_refine >= REFINE_CAP:
        return 0.0
    return _RATE.get(current_refine, 0.1)


def refine_ore_for(slot: str) -> str:
    return "oridecon" if slot == "weapon" else "elunium"


def refine_zeny_cost(current_refine: int) -> int:
    return (current_refine + 1) * 200


def attempt_refine(current_refine: int, rng: random.Random) -> tuple[int, bool]:
    if current_refine >= REFINE_CAP:
        return current_refine, False
    if rng.random() < success_rate(current_refine):
        return current_refine + 1, True
    return max(0, current_refine - 1), False


def attempt_random_refine(current_refine: int, rng: random.Random) -> tuple[int, int]:
    if current_refine >= REFINE_CAP:
        return current_refine, 0
    roll = rng.random()
    if roll < 0.10:
        increment = 0
    elif roll < 0.60:
        increment = 1
    elif roll < 0.95:
        increment = 2
    else:
        increment = 3
    new_refine = min(REFINE_CAP, current_refine + increment)
    return new_refine, new_refine - current_refine


REFINE_BONUS_PER_LEVEL = {"atk": 2, "matk": 2, "def": 1, "mdef": 1,
                          "max_hp": 15, "flee": 1, "hit": 1, "crit": 1}


def refine_stat_bonus(base_stats: dict, refine: int) -> dict:
    return {k: REFINE_BONUS_PER_LEVEL.get(k, 0) * refine
            for k in base_stats if k in REFINE_BONUS_PER_LEVEL}
