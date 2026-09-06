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


def test_choose_returns_value_by_number(monkeypatch):
    from client import app
    from rich.console import Console
    answers = iter(["2"])
    monkeypatch.setattr("client.app.Prompt.ask", lambda *a, **k: next(answers))
    rows = [("甲", "a"), ("乙", "b"), ("丙", "c")]
    assert app._choose(Console(record=True), "選一個", rows) == "b"


def test_choose_zero_returns_none(monkeypatch):
    from client import app
    from rich.console import Console
    monkeypatch.setattr("client.app.Prompt.ask", lambda *a, **k: "0")
    assert app._choose(Console(record=True), "選一個", [("甲", "a")]) is None


def test_choose_reprompts_on_garbage(monkeypatch):
    from client import app
    from rich.console import Console
    answers = iter(["x", "99", "1"])
    monkeypatch.setattr("client.app.Prompt.ask", lambda *a, **k: next(answers))
    assert app._choose(Console(record=True), "選一個", [("甲", "a"), ("乙", "b")]) == "a"


def test_choose_empty_rows_returns_none(monkeypatch):
    from client import app
    from rich.console import Console
    assert app._choose(Console(record=True), "空", []) is None


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
    answers = iter(["1", "1", "1", "0"])
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: next(answers)))
    rec = _RecApi()
    menus.stats_menu(rec, {"id": 1, "base_level": 10, "job_id": "swordman",
                           "stat_str": 1, "stat_agi": 1, "stat_vit": 1,
                           "stat_int": 1, "stat_dex": 1, "stat_luk": 1}, Console(record=True))
    assert ("allocate_stats", 1, {"str": 3}) in rec.calls


def test_stats_menu_shows_costs_and_batches(monkeypatch):
    from client.menus import stats_menu
    calls = {}

    class FakeApi:
        def allocate_stats(self, cid, deltas):
            calls["deltas"] = deltas
            return {"stat_str": 1 + deltas.get("str", 0)}

    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("client.menus.Prompt.ask", lambda *a, **k: next(answers))
    from rich.console import Console
    stats_menu(FakeApi(), {"id": 1, "base_level": 20,
                           "stat_str": 1, "stat_agi": 1, "stat_vit": 1,
                           "stat_int": 1, "stat_dex": 1, "stat_luk": 1},
               Console())
    assert calls["deltas"] == {"str": 2}


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


class _SocialApi:
    def __init__(self, mine=None, guilds=None, pending=None):
        self.calls = []
        self._mine = mine
        self._guilds = guilds if guilds is not None else [
            {"id": 1, "name": "波利團", "member_count": 2}
        ]
        self._pending = pending if pending is not None else []

    def leaderboard(self, by="base_level"):
        self.calls.append(("leaderboard", by))
        return [{"character_name": "高手", "account": "a", "value": 40}]

    def guild_mine(self):
        return self._mine

    def guild_list(self):
        return self._guilds

    def guild_join(self, gid):
        self.calls.append(("guild_join", gid))

    def guild_create(self, name):
        self.calls.append(("guild_create", name))

    def guild_leave(self):
        self.calls.append(("guild_leave",))

    def trade_pending(self):
        return self._pending

    def trade_offer(self, who):
        self.calls.append(("trade_offer", who))
        return {"trade_id": 7}

    def trade_get(self, tid):
        return {"id": tid, "status": "open", "from_confirmed": 0,
                "to_confirmed": 0, "items": []}

    def trade_cancel(self, tid):
        self.calls.append(("trade_cancel", tid))
        return {"status": "cancelled"}


def test_rank_menu_calls_leaderboard(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "zeny"))
    rec = _SocialApi()
    menus.rank_menu(rec, {"id": 1}, Console(record=True))
    assert ("leaderboard", "zeny") in rec.calls


def test_guild_menu_create(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "create 波利獵人團"))
    rec = _SocialApi(mine=None)
    menus.guild_menu(rec, {"id": 1}, Console(record=True))
    assert ("guild_create", "波利獵人團") in rec.calls


def test_guild_menu_join(monkeypatch):
    from client import menus
    from rich.console import Console
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "join 1"))
    rec = _SocialApi(mine=None)
    menus.guild_menu(rec, {"id": 1}, Console(record=True))
    assert ("guild_join", 1) in rec.calls


def test_trade_menu_opens_new_then_cancel(monkeypatch):
    from client import menus
    from rich.console import Console
    answers = iter(["new", "bob", "cancel"])
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: next(answers)))
    rec = _SocialApi()
    menus.trade_menu(rec, {"id": 1}, Console(record=True))
    assert ("trade_offer", "bob") in rec.calls
    assert ("trade_cancel", 7) in rec.calls
