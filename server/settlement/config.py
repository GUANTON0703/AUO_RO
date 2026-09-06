from dataclasses import dataclass


@dataclass
class HuntConfig:
    offline_efficiency: float = 0.6
    offline_cap_hours: int = 8
    round_seconds: float = 2.0
    rest_seconds: float = 3.0
    sp_regen_per_sec: float = 1.0
    hp_regen_frac_per_sec: float = 0.004   # 每秒回復 max_hp 的 0.4%（場間自然回血）
    potion_hp_threshold: float = 0.5
    card_pity_threshold: int = 800
    rare_drop_cutoff: float = 0.02
    literal_sim_kill_cap: int = 300
    find_monster_rate: float = 0.02
    fly_wing_rate: float = 0.05
    boss_retreat_rate: float = 0.01
    experience_multiplier: float = 1.0
    drop_multiplier: float = 1.0

    @classmethod
    def from_settings(cls, settings) -> "HuntConfig":
        experience_multiplier = 1.0
        drop_multiplier = 1.0
        try:
            from server.db import connection
            with connection.get_connection() as conn:
                rows = conn.execute(
                    "SELECT key, value FROM server_settings WHERE key IN (?, ?)",
                    ("experience_multiplier", "drop_multiplier"),
                ).fetchall()
            values = {row[0]: float(row[1]) for row in rows}
            experience_multiplier = values.get("experience_multiplier", 1.0)
            drop_multiplier = values.get("drop_multiplier", 1.0)
        except (RuntimeError, OSError):
            pass
        return cls(
            offline_efficiency=settings.offline_efficiency,
            offline_cap_hours=settings.offline_cap_hours,
            experience_multiplier=experience_multiplier,
            drop_multiplier=drop_multiplier,
        )
