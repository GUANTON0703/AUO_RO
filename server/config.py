from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROTXT_", env_file=".env", extra="ignore")

    db_path: str = "rotxt.db"
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    token_ttl_hours: int = 720
    max_characters_per_account: int = 3
    starting_map: str = "prontera_east_gate"
    # 公開註冊碼：填了之後，用這個碼註冊不限次數、不消耗（給朋友用網址 + 碼進來）
    open_invite_code: str = "99auo99"

    stat_reset_free: bool = True
    skill_reset_free: bool = True

    offline_efficiency: float = 0.6
    offline_cap_hours: int = 8
    online_grace_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
