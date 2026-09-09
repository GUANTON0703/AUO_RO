from pydantic import BaseModel


class AccountPublic(BaseModel):
    id: int
    username: str


class CharacterPublic(BaseModel):
    id: int
    name: str
    job_id: str
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
    stat_points: int  # 可用屬性點（算出來的，非 DB 欄位值）
    skill_points: int  # 可用技能點（算出來的，非 DB 欄位值）
    is_rebirth: bool = False
    zeny: int
    location_map: str
    learned_skills: dict[str, int] = {}
