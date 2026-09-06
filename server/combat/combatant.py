from dataclasses import dataclass, field

from shared.content import MonsterDef


@dataclass
class ResolvedSkill:
    skill_id: str
    name: str
    level: int
    kind: str                 # active / passive
    sp_cost: int
    cooldown_rounds: int
    effects: list[dict]
    trigger: str              # every_turn / hp_below_50 / hp_below_30 / sp_available / cooldown_ready
    priority: int
    _cd_left: int = 0

    def effect_value(self, key: str):
        """從 effects 裡找出帶 key 的那筆，取對應 level 的值（level 1 → index 0）。"""
        for e in self.effects:
            if key in e:
                seq = e[key]
                if isinstance(seq, list):
                    return seq[min(self.level, len(seq)) - 1]
                return seq
        return None


@dataclass
class Combatant:
    name: str
    max_hp: int
    max_sp: int
    atk: int
    matk: int
    defense: int
    mdef: int
    hit: int
    flee: int
    aspd: int
    crit: int
    is_caster: bool = False
    skills: list[ResolvedSkill] = field(default_factory=list)
    statuses: list = field(default_factory=list)  # server.combat.status.Status
    hp: int = field(default=0)
    sp: int = field(default=0)

    def __post_init__(self):
        if self.hp == 0:
            self.hp = self.max_hp
        if self.sp == 0:
            self.sp = self.max_sp

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - max(0, amount))

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + max(0, amount))

    def spend_sp(self, amount: int) -> bool:
        if self.sp < amount:
            return False
        self.sp -= amount
        return True

    @classmethod
    def from_monster(cls, m: MonsterDef) -> "Combatant":
        s = m.stats
        return cls(
            name=m.name, max_hp=s.max_hp, max_sp=s.max_sp, atk=s.atk, matk=s.matk,
            defense=s.defense, mdef=s.mdef, hit=s.hit, flee=s.flee, aspd=s.aspd,
            crit=s.crit, is_caster=(s.matk > s.atk),
        )
