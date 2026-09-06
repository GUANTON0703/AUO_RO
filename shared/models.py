from enum import Enum

from pydantic import BaseModel


class JobId(str, Enum):
    NOVICE = "novice"
    SWORDMAN = "swordman"
    MAGE = "mage"
    ARCHER = "archer"
    ACOLYTE = "acolyte"
    MERCHANT = "merchant"
    THIEF = "thief"


class AccountPublic(BaseModel):
    id: int
    username: str


class CharacterPublic(BaseModel):
    id: int
    name: str
    job_id: JobId
    base_level: int
    job_level: int
    base_exp: int
    job_exp: int
    stat_str: int
    stat_agi: int
    stat_vit: int
    stat_int: int
    stat_dex: int
    stat_luk: int
    stat_points: int
    skill_points: int
    zeny: int
    location_map: str
