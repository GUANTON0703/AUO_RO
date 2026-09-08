from dataclasses import dataclass, field
import random


@dataclass
class HuntStrategy:
    include_monsters: list[str] = field(default_factory=list)
    exclude_monsters: list[str] = field(default_factory=list)
    flee_on_boss: bool = True
    auto_potion: bool = True
    potion_item_id: str | None = None          # 指定喝哪瓶，None = 自動挑回血最多的
    potion_hp_pct: float = 0.5                  # 血量低於此比例才喝（0~1）
    auto_buy_potion: bool = False               # 掛機時自動補水
    buy_potion_id: str | None = None            # 買哪瓶，None = red_potion
    buy_potion_upto: int = 0                    # 補到手上有這麼多瓶
    sell_item_ids: list[str] = field(default_factory=list)   # 每次結算自動賣掉這些道具
    skill_min_sp_pct: float = 0.0              # SP 高於此比例才放主動技能（0 = 一律放）
    primary_skill_id: str | None = None        # 指定主攻技能（None = 引擎自動挑）
    skill_toggles: dict[str, bool] = field(default_factory=dict)  # {技能id: 掛機要不要放}

    def allows(self, monster_id: str) -> bool:
        return monster_id not in self.exclude_monsters and (
            not self.include_monsters or monster_id in self.include_monsters
        )


def choose_hunt_event(is_boss: bool, rng: random.Random, cfg):
    from server.settlement.events import FindMonsterEvent, FlyWingEvent, BossRetreatEvent
    if rng.random() < cfg.find_monster_rate:
        return FindMonsterEvent()
    if rng.random() < cfg.fly_wing_rate:
        return FlyWingEvent()
    if is_boss and rng.random() < cfg.boss_retreat_rate:
        return BossRetreatEvent()
    return None
