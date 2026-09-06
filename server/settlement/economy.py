from shared.content import MonsterDef


def zeny_per_kill(m: MonsterDef) -> int:
    return round(m.level * 1.5 + m.base_exp * 0.3)
