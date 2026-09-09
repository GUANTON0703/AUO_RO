from shared.content import CombatStats, MonsterRole

# 角色定位係數：(hp, atk, def, flee)
_ROLE = {
    "glass":  (0.7, 1.3, 0.0, 1.2),
    "normal": (1.0, 1.0, 0.5, 1.0),
    "tank":   (1.8, 0.8, 1.5, 0.7),
    # MVP 戰鬥要有明確的長線壓力：同級畢業裝約 30~80 回合，
    # 但仍保留可撤退、弱角色會輸的風險。
    "boss":   (4.5, 2.0, 2.1, 1.0),
}


def baseline(level: int, role: MonsterRole) -> CombatStats:
    hp_mult, atk_mult, def_mult, flee_mult = _ROLE[role]

    # 基準：Lv1 約 HP 50 / ATK 8；隨等級指數偏線性成長
    hp_base = 40 + 20 * level + 0.9 * level**2
    atk_base = 5 + 1.6 * level
    def_base = 0.6 * level
    # 命中要跟得上玩家 FLEE（= base_level + AGI + 裝備）。原本 level+1 讓任何
    # 有練 AGI 的角色都能對中高階怪 100% 迴避，太誇張。
    hit_base = round(level * 1.4) + 10
    flee_base = level + 5
    matk_base = 3 + 1.2 * level
    mdef_base = 0.3 * level

    return CombatStats(
        max_hp=max(1, round(hp_base * hp_mult)),
        max_sp=0,
        atk=max(0, round(atk_base * atk_mult)),
        matk=max(0, round(matk_base * (1.4 if role == "boss" else 1.0))),
        defense=max(0, round(def_base * def_mult)),
        mdef=max(0, round(mdef_base)),
        hit=max(0, round(hit_base * (1.5 if role == "boss" else 1.0))),
        flee=max(0, round(flee_base * flee_mult)),
        aspd=110 if role == "boss" else 100,
        crit=5 if role == "boss" else 0,
    )
