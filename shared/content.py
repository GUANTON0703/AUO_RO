from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Element(str, Enum):
    NEUTRAL = "neutral"
    WATER = "water"
    EARTH = "earth"
    FIRE = "fire"
    WIND = "wind"
    POISON = "poison"
    HOLY = "holy"
    SHADOW = "shadow"
    GHOST = "ghost"
    UNDEAD = "undead"


class Race(str, Enum):
    ANIMAL = "animal"      # 動物系
    PLANT = "plant"        # 植物系
    INSECT = "insect"      # 昆蟲系
    DEMON = "demon"        # 惡魔系
    UNDEAD = "undead"      # 不死系
    DEMIHUMAN = "demihuman"  # 人形系
    ANGEL = "angel"       # 天使系 / 聖靈系
    DRAGON = "dragon"      # 龍族
    FORMLESS = "formless"  # 無形 / 精靈系
    FISH = "fish"         # 魚貝系


class Size(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Stat(str, Enum):
    STR = "str"
    AGI = "agi"
    VIT = "vit"
    INT = "int"
    DEX = "dex"
    LUK = "luk"


MonsterRole = Literal["tank", "normal", "glass", "boss"]


class CombatStats(BaseModel):
    max_hp: int = Field(ge=1)
    max_sp: int = Field(ge=0)
    atk: int = Field(ge=0)
    matk: int = Field(ge=0)
    defense: int = Field(ge=0)   # 硬防（百分比減傷用），欄位名避開 python 保留字
    mdef: int = Field(ge=0)
    hit: int = Field(ge=0)
    flee: int = Field(ge=0)
    aspd: int = Field(ge=1)      # 每 100 = 一次普攻 / 回合的基準；換算見戰鬥引擎階段
    crit: int = Field(ge=0)


class DropEntry(BaseModel):
    item_id: str
    rate: float = Field(ge=0.0, le=1.0)   # 0~1 機率；卡片這種低機率也照這個欄位
    min_qty: int = Field(default=1, ge=1)
    max_qty: int = Field(default=1, ge=1)


class MonsterDef(BaseModel):
    id: str
    name: str
    level: int = Field(ge=1)
    element: Element
    race: Race
    size: Size
    role: MonsterRole
    base_exp: int = Field(ge=0)
    job_exp: int = Field(ge=0)
    stats: CombatStats
    drops: list[DropEntry] = Field(default_factory=list)
    is_mvp: bool = False
    lore: str = ""


class MapDef(BaseModel):
    id: str
    name: str
    town: Literal["prontera", "morroc", "payon", "geffen", "aldebaran"]
    level_range: list[int] = Field(min_length=2, max_length=2)
    monster_ids: list[str] = Field(default_factory=list)
    mvp_id: str | None = None
    unlock_base_level: int = Field(ge=1)


class MvpDef(MonsterDef):
    cooldown_hours: int = Field(ge=1)
    home_map_id: str


class SkillDef(BaseModel):
    id: str
    name: str
    job_id: str
    kind: Literal["active", "passive"]
    max_level: int = Field(ge=1, le=10)
    sp_cost: list[int] = Field(default_factory=list)
    cooldown_s: float = 0.0
    effects: list[dict] = Field(default_factory=list)   # 型別化延到戰鬥引擎階段
    idle_default: dict = Field(default_factory=dict)
    requires: dict[str, int] = Field(default_factory=dict)  # {前置技能id: 需要等級}


class JobDef(BaseModel):
    id: str
    name: str
    tier: Literal["novice", "first", "second", "third"]
    parent_id: str | None = None
    change_job_level: int = Field(default=10, ge=1)   # 轉入此職所需的前職 Job Level
    hp_per_level: float = Field(gt=0)
    sp_per_level: float = Field(ge=0)
    skill_ids: list[str] = Field(default_factory=list)


class EquipmentDef(BaseModel):
    id: str
    name: str
    slot: Literal["weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"]
    rarity: Literal["common", "fine", "legendary"]
    stats: dict = Field(default_factory=dict)
    element: str = "neutral"          # 武器屬性；防具留 neutral
    refinable: bool = True
    card_slots: int = Field(default=0, ge=0, le=4)
    job_ids: list[str] = Field(default_factory=list)   # 空 = 全職可用
    required_level: int = Field(default=1, ge=1)
    npc_buy: int | None = None    # NPC 售價（None = NPC 不賣）
    npc_sell: int = Field(default=0, ge=0)


class CardDef(BaseModel):
    id: str
    name: str
    monster_id: str
    slot: Literal["weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"]
    drop_rate: float = Field(gt=0.0, le=1.0)
    effects: list[dict] = Field(default_factory=list)


class ItemDef(BaseModel):
    id: str
    name: str
    kind: Literal["consumable", "material", "misc"]
    effects: list[dict] = Field(default_factory=list)
    required_level: int = Field(default=1, ge=1)   # 消耗品的使用/購買等級門檻
    npc_buy: int | None = None    # NPC 售價（None = NPC 不賣）
    npc_sell: int = Field(default=0, ge=0)


class ElementChart(BaseModel):
    table: dict[str, dict[str, float]] = Field(default_factory=dict)

    def multiplier(self, attacker: str, defender: str) -> float:
        return self.table.get(attacker, {}).get(defender, 1.0)
