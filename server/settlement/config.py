from dataclasses import dataclass


@dataclass
class HuntConfig:
    offline_efficiency: float = 0.6
    offline_cap_hours: int = 8
    round_seconds: float = 2.0
    rest_seconds: float = 3.0
    sp_regen_per_sec: float = 1.0
    potion_hp_threshold: float = 0.5
    card_pity_threshold: int = 800
    rare_drop_cutoff: float = 0.02
    literal_sim_kill_cap: int = 300

    @classmethod
    def from_settings(cls, settings) -> "HuntConfig":
        return cls(
            offline_efficiency=settings.offline_efficiency,
            offline_cap_hours=settings.offline_cap_hours,
        )
