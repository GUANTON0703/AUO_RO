from server.settlement.config import HuntConfig


def test_defaults_match_design():
    c = HuntConfig()
    assert c.offline_efficiency == 0.6
    assert c.offline_cap_hours == 8
    assert c.round_seconds == 2.0
    assert c.rest_seconds == 3.0
    assert c.sp_regen_per_sec == 1.0
    assert 0.0 < c.potion_hp_threshold < 1.0
    assert c.card_pity_threshold >= 100


def test_from_settings_reads_env(monkeypatch):
    monkeypatch.setenv("ROTXT_OFFLINE_EFFICIENCY", "0.8")
    monkeypatch.setenv("ROTXT_OFFLINE_CAP_HOURS", "12")
    from server.config import Settings
    c = HuntConfig.from_settings(Settings())
    assert c.offline_efficiency == 0.8
    assert c.offline_cap_hours == 12
