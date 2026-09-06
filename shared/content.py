from enum import Enum


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
