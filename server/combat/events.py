from dataclasses import dataclass, field


@dataclass
class CombatEvent:
    kind: str = field(init=False, default="event")
    # 事件產生當下，玩家的即時 HP/SP（由 engine 產生事件時貼上）。前端照事件播放
    # 節奏同步血條/魔條，用這個而不是每次輪詢就整條線跳到最終值，才有臨場感。
    player_hp: int | None = field(init=False, default=None)
    player_sp: int | None = field(init=False, default=None)


@dataclass
class AttackEvent(CombatEvent):
    actor: str
    target: str
    damage: int
    crit: bool
    hit: bool

    def __post_init__(self):
        self.kind = "attack"


@dataclass
class SkillEvent(CombatEvent):
    actor: str
    target: str
    skill_id: str
    skill_name: str
    damage: int = 0
    sp_cost: int = 0    # 這次施放實際扣掉的 SP（consumes_all_sp 技能會是當下全部庫存）

    def __post_init__(self):
        self.kind = "skill"


@dataclass
class HealEvent(CombatEvent):
    actor: str
    target: str
    amount: int
    source: str = "skill"      # "skill" 或 "potion"

    def __post_init__(self):
        self.kind = "heal"


@dataclass
class KillEvent(CombatEvent):
    actor: str
    target: str

    def __post_init__(self):
        self.kind = "kill"


@dataclass
class StatusAppliedEvent(CombatEvent):
    actor: str
    target: str
    status: str
    duration: int

    def __post_init__(self):
        self.kind = "status_applied"


@dataclass
class StatusExpiredEvent(CombatEvent):
    target: str
    status: str

    def __post_init__(self):
        self.kind = "status_expired"


@dataclass
class DotEvent(CombatEvent):
    target: str
    status: str
    damage: int

    def __post_init__(self):
        self.kind = "dot"


@dataclass
class FledEvent(CombatEvent):
    actor: str
    hp: int

    def __post_init__(self):
        self.kind = "fled"
