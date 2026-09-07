import random


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _mods(base: float, element_multiplier: float, resist_pct: int, race_pct: int) -> float:
    return (base * element_multiplier
            * (1 + max(0, race_pct) / 100)
            * (1 - _clamp(resist_pct, -100, 100) / 100))


def physical_damage(atk: int, target_defense: int, element_multiplier: float = 1.0,
                    soft_def: int = 0, resist_pct: int = 0, race_pct: int = 0) -> int:
    reduction = _clamp(target_defense, 0, 95) / 100
    raw = _mods(atk * (1 - reduction), element_multiplier, resist_pct, race_pct)
    return max(1, round(raw) - max(0, soft_def))


def magic_damage(matk: int, target_mdef: int, element_multiplier: float = 1.0,
                 soft_mdef: int = 0, resist_pct: int = 0, race_pct: int = 0) -> int:
    reduction = _clamp(target_mdef, 0, 95) / 100
    raw = _mods(matk * (1 - reduction), element_multiplier, resist_pct, race_pct)
    return max(1, round(raw) - max(0, soft_mdef))


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
