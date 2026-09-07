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
    zeny_multiplier: float = 1.0
    settle_floor_seconds: float = 3.0    # 結算防抖：距上次結算未達這個秒數就只回累積值
    huntable_win_rate: float = 0.85      # 自動選怪 / 輪替時，勝率低於此值的怪不打

    @classmethod
    def from_settings(cls, settings) -> "HuntConfig":
        defaults = cls()
        experience_multiplier = defaults.experience_multiplier
        drop_multiplier = defaults.drop_multiplier
        zeny_multiplier = defaults.zeny_multiplier
        settle_floor_seconds = defaults.settle_floor_seconds
        huntable_win_rate = defaults.huntable_win_rate
        try:
            from server.db import connection
            with connection.get_connection() as conn:
                rows = conn.execute(
                    "SELECT key, value FROM server_settings WHERE key IN (?, ?, ?, ?, ?)",
                    (
                        "experience_multiplier",
                        "drop_multiplier",
                        "zeny_multiplier",
                        "settle_floor_seconds",
                        "huntable_win_rate",
                    ),
                ).fetchall()
            values = {row[0]: float(row[1]) for row in rows}
            experience_multiplier = values.get("experience_multiplier", experience_multiplier)
            drop_multiplier = values.get("drop_multiplier", drop_multiplier)
            zeny_multiplier = values.get("zeny_multiplier", zeny_multiplier)
            settle_floor_seconds = values.get("settle_floor_seconds", settle_floor_seconds)
            huntable_win_rate = values.get("huntable_win_rate", huntable_win_rate)
        except (RuntimeError, OSError):
            pass
        return cls(
            offline_efficiency=settings.offline_efficiency,
            offline_cap_hours=settings.offline_cap_hours,
            experience_multiplier=experience_multiplier,
            drop_multiplier=drop_multiplier,
            zeny_multiplier=zeny_multiplier,
            settle_floor_seconds=settle_floor_seconds,
            huntable_win_rate=huntable_win_rate,
        )
