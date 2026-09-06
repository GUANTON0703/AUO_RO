import importlib

from server import config


def test_defaults():
    s = config.Settings()
    assert s.db_path == "rotxt.db"
    assert s.server_host == "127.0.0.1"
    assert s.server_port == 8000
    assert s.token_ttl_hours == 720
    assert s.max_characters_per_account == 3
    assert s.starting_map == "prontera_east_gate"
    assert 0.0 < s.offline_efficiency <= 1.0
    assert s.offline_cap_hours == 8


def test_env_override(monkeypatch):
    monkeypatch.setenv("ROTXT_DB_PATH", "/tmp/other.db")
    monkeypatch.setenv("ROTXT_MAX_CHARACTERS_PER_ACCOUNT", "5")
    s = config.Settings()
    assert s.db_path == "/tmp/other.db"
    assert s.max_characters_per_account == 5


def test_get_settings_is_cached():
    importlib.reload(config)
    assert config.get_settings() is config.get_settings()
