from dataclasses import dataclass, field
import random


@dataclass
class HuntStrategy:
    include_monsters: list[str] = field(default_factory=list)
    exclude_monsters: list[str] = field(default_factory=list)
    flee_on_boss: bool = True
    auto_potion: bool = True
    potion_item_id: str | None = None
    buy_potions: bool = False
    sell_items: bool = False

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
