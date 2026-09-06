from dataclasses import dataclass, field


@dataclass
class CombatEvent:
    kind: str = field(init=False, default="event")


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

    def __post_init__(self):
        self.kind = "skill"


@dataclass
class HealEvent(CombatEvent):
    actor: str
    target: str
    amount: int

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
class FledEvent(CombatEvent):
    actor: str
    hp: int

    def __post_init__(self):
        self.kind = "fled"
