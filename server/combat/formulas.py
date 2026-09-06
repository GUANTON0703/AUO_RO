import random


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def physical_damage(atk: int, target_defense: int, element_multiplier: float = 1.0) -> int:
    reduction = _clamp(target_defense, 0, 95) / 100
    return max(1, round(atk * (1 - reduction) * element_multiplier))


def magic_damage(matk: int, target_mdef: int, element_multiplier: float = 1.0) -> int:
    reduction = _clamp(target_mdef, 0, 95) / 100
    return max(1, round(matk * (1 - reduction) * element_multiplier))


def hit_chance(attacker_hit: int, target_flee: int) -> float:
    return _clamp(80 + attacker_hit - target_flee, 5, 95) / 100


def crit_chance(attacker_crit: int) -> float:
    return _clamp(attacker_crit, 0, 100) / 100


CRIT_MULTIPLIER = 1.4


def attacks_this_round(aspd: int, rng: random.Random) -> int:
    whole = aspd // 100
    frac = (aspd % 100) / 100
    extra = 1 if rng.random() < frac else 0
    return max(1, whole + extra)
