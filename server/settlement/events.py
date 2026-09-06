from dataclasses import dataclass


@dataclass
class KillBatchEvent:
    monster_name: str
    count: int
    base_exp: int
    job_exp: int
    zeny: int
    kind: str = "kill_batch"


@dataclass
class RareDropEvent:
    item_id: str
    item_name: str
    qty: int
    kind: str = "rare_drop"


@dataclass
class PotionUsedEvent:
    item_id: str
    item_name: str
    count: int
    remaining: int
    kind: str = "potion_used"


@dataclass
class RetreatEvent:
    reason: str
    seconds_survived: float
    kind: str = "retreat"


@dataclass
class FindMonsterEvent:
    kind: str = "find_monster"


@dataclass
class FlyWingEvent:
    kind: str = "fly_wing"


@dataclass
class BossRetreatEvent:
    kind: str = "boss_retreat"
