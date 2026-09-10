import random


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _mods(base: float, element_multiplier: float, resist_pct: int, race_pct: int) -> float:
    return (base * element_multiplier
            * (1 + max(0, race_pct) / 100)
            * (1 - _clamp(resist_pct, -100, 100) / 100))


# 防禦用「遞減報酬」：reduction = def / (def + K)。Pre-Renewal 小數值尺度，
# 重甲角色 DEF 約 50~90 → 減傷 50~65%，永遠到不了 100%。
_DEF_K = 45


def _dmg_reduction(defense: int) -> float:
    d = max(0, defense)
    return d / (d + _DEF_K)


def _variance(rng) -> float:
    """每擊 ±12% 的隨機浮動（原版武器攻擊 min~max 的簡化）。"""
    return rng.uniform(0.88, 1.12) if rng is not None else 1.0


def physical_damage(atk: int, target_defense: int, element_multiplier: float = 1.0,
                    soft_def: int = 0, resist_pct: int = 0, race_pct: int = 0,
                    rng=None) -> int:
    raw = _mods(atk * (1 - _dmg_reduction(target_defense)),
                element_multiplier, resist_pct, race_pct)
    return max(1, round(raw * _variance(rng)) - max(0, soft_def))


def magic_damage(matk: int, target_mdef: int, element_multiplier: float = 1.0,
                 soft_mdef: int = 0, resist_pct: int = 0, race_pct: int = 0,
                 rng=None) -> int:
    raw = _mods(matk * (1 - _dmg_reduction(target_mdef)),
                element_multiplier, resist_pct, race_pct)
    return max(1, round(raw * _variance(rng)) - max(0, soft_mdef))


def hit_chance(attacker_hit: int, target_flee: int) -> float:
    return _clamp(80 + attacker_hit - target_flee, 5, 95) / 100


def crit_chance(attacker_crit: int) -> float:
    return _clamp(attacker_crit, 0, 100) / 100


CRIT_MULTIPLIER = 1.4


def attacks_this_round(aspd: int, rng: random.Random) -> int:
    """每回合普攻次數。基準 aspd 100 = 1 擊，攻速上限 193 = 3 擊，中間線性內插，
    小數部分用機率決定要不要多一擊。"""
    expected = 1.0 + max(0, aspd - 100) / 46.5
    whole = int(expected)
    extra = 1 if rng.random() < (expected - whole) else 0
    return max(1, whole + extra)
