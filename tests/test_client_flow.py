import pytest
from fastapi.testclient import TestClient

from client.api import ApiClient
from client.auth_flow import ensure_logged_in, select_or_create_character
from client.config import SessionStore
from server.app import create_app
from server.db import connection


def test_session_store_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(server_url="http://x", token="tok", username="u")
    loaded = SessionStore(tmp_path / "s.json").load()
    assert loaded["token"] == "tok" and loaded["username"] == "u"


def test_session_store_missing_returns_none(tmp_path):
    assert SessionStore(tmp_path / "none.json").load() is None


@pytest.fixture
def api(tmp_path):
    connection.configure(str(tmp_path / "c.db"))
    connection.init_db()
    from server.auth import invites

    code = invites.create_invite()
    return ApiClient(TestClient(create_app())), code


def test_ensure_logged_in_register_happy_path(api, tmp_path, monkeypatch):
    client, code = api
    store = SessionStore(tmp_path / "s.json")
    answers = iter([code, "brandnew", "password123", "小新"])
    monkeypatch.setattr(
        "client.auth_flow.Prompt.ask",
        lambda *a, **k: "2" if "登入" in (a[0] if a else "") else next(answers),
    )
    ensure_logged_in(client, store, "http://test")
    assert client.token is not None
    assert store.load()["username"] == "brandnew"

    ch = select_or_create_character(client)
    assert ch["name"]


def test_ensure_logged_in_reuses_saved_token(api, tmp_path, monkeypatch):
    client, code = api
    client.register(code, "returning", "password123")
    client.login("returning", "password123")
    store = SessionStore(tmp_path / "s.json")
    store.save(server_url="http://test", token=client.token, username="returning")

    fresh = ApiClient(client._http)

    def _boom(*a, **k):
        raise AssertionError("不應該再問一次")

    monkeypatch.setattr("client.auth_flow.Prompt.ask", _boom)
    ensure_logged_in(fresh, store, "http://test")
    assert fresh.token == client.token


class _RecApi:
    def __init__(self):
        self.calls = []

    def inventory(self, cid):
        return {"items": {}, "equipment": [
            {"id": 3, "equipment_id": "knife", "refine": 4, "equipped_slot": None, "card_ids": []}
        ]}

    def shop(self):
        return {"items": [{"id": "red_potion", "name": "紅藥", "price": 50, "kind": "consumable"}],
                "equipment": []}

    def allocate_stats(self, cid, deltas):
        self.calls.append(("allocate_stats", cid, deltas))
        return {"message": "ok"}

    def buy(self, item_id, qty=1):
        self.calls.append(("buy", item_id, qty))
        return {"ok": True, "spent": qty * 50}

    def refine(self, cid, inst_id):
        self.calls.append(("refine", cid, inst_id))
        return {"success": True, "refine": 5, "message": "精煉成功"}


def test_stats_menu_calls_allocate(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "str"))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 3))
    rec = _RecApi()
    menus.stats_menu(rec, {"id": 1, "base_level": 10, "job_id": "swordman"}, Console(record=True))
    assert ("allocate_stats", 1, {"str": 3}) in rec.calls


def test_shop_menu_buys(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(
        lambda *a, **k: "buy" if k.get("choices") else "red_potion"))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 5))
    rec = _RecApi()
    menus.shop_menu(rec, {"id": 1}, Console(record=True))
    assert ("buy", "red_potion", 5) in rec.calls


def test_refine_menu_calls_refine(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "cancel"))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 3))
    monkeypatch.setattr(menus.Confirm, "ask", staticmethod(lambda *a, **k: True))
    rec = _RecApi()
    menus.refine_menu(rec, {"id": 1}, Console(record=True))
    assert ("refine", 1, 3) in rec.calls


class _MvpApi:
    def __init__(self):
        self.calls = []

    def list_mvp(self):
        return [
            {"id": "angel_poring", "name": "天使波利", "level": 16,
             "home_map_id": "mjolnir_mine", "home_map_name": "礦洞",
             "available": True, "seconds_remaining": 0, "cooldown_hours": 8},
            {"id": "queen_bee", "name": "蜂后", "level": 19,
             "home_map_id": "x", "home_map_name": "南野", "available": False,
             "seconds_remaining": 7200, "cooldown_hours": 12},
        ]

    def challenge_mvp(self, mvp_id, flee_hp_frac=None):
        self.calls.append(("challenge_mvp", mvp_id, flee_hp_frac))
        return {"outcome": "win", "rounds": 12, "base_exp": 500, "job_exp": 200,
                "zeny": 3000, "exp_penalty": 0,
                "drops": {"angel_poring_card": 1}, "events": [
                    {"kind": "attack", "actor": "T", "target": "天使波利",
                     "damage": 50, "crit": False, "hit": True},
                    {"kind": "challenge_result", "outcome": "win", "rounds": 12,
                     "base_exp": 500, "job_exp": 200, "zeny": 3000,
                     "exp_penalty": 0, "drops": {"angel_poring_card": 1}},
                ]}


def test_mvp_menu_challenges(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "angel_poring"))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 15))
    monkeypatch.setattr(menus.Confirm, "ask", staticmethod(lambda *a, **k: True))
    rec = _MvpApi()
    menus.mvp_menu(rec, {"id": 1}, Console(record=True))
    assert ("challenge_mvp", "angel_poring", 0.15) in rec.calls
