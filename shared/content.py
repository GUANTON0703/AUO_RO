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
    rate: float = Field(gt=0.0, le=1.0)   # 0~1 機率；卡片這種低機率也照這個欄位
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
