"""攻擊時附加的異常狀態定義。卡片 on_hit_proc 與部分技能 debuff 共用。"""


def apply_ailment(target, name: str, rng, events: list) -> bool:
    """對 target 施加一個異常狀態。回傳是否成功（被免疫則否）。"""
    from server.combat.status import Status, apply_status

    if name in getattr(target, "immunities", set()):
        return False
    if name in ("stun", "freeze", "stone", "sleep"):
        dur = {"stun": 2, "freeze": 3, "stone": 3, "sleep": 3}[name]
        apply_status(target, Status(kind="disable", name=name, duration=dur,
                                    magnitude=0), events)
    elif name == "silence":
        apply_status(target, Status(kind="silence", name="silence", duration=3,
                                    magnitude=0), events)
    elif name == "blind":
        apply_status(target, Status(kind="stat_mod", name="blind", duration=4,
                                    magnitude=-25, stat="hit"), events)
        apply_status(target, Status(kind="stat_mod", name="blind_flee", duration=4,
                                    magnitude=-25, stat="flee"))
    elif name == "curse":
        apply_status(target, Status(kind="stat_mod", name="curse", duration=5,
                                    magnitude=-20, stat="aspd"), events)
        apply_status(target, Status(kind="stat_mod", name="curse_crit", duration=5,
                                    magnitude=-10, stat="crit"))
    elif name in ("bleed", "poison"):
        per_tick = round(target.max_hp * 0.012) + 8
        apply_status(target, Status(kind="dot", name=name, duration=4,
                                    magnitude=per_tick), events)
    else:
        return False
    return True
