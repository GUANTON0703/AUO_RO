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
    from client.ui import choose
    from rich.console import Console
    answers = iter(["2"])
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: next(answers))
    rows = [("甲", "a"), ("乙", "b"), ("丙", "c")]
    assert choose(Console(record=True), "選一個", rows) == "b"


def test_choose_zero_returns_none(monkeypatch):
    from client.ui import choose
    from rich.console import Console
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: "0")
    assert choose(Console(record=True), "選一個", [("甲", "a")]) is None


def test_choose_reprompts_on_garbage(monkeypatch):
    from client.ui import choose
    from rich.console import Console
    answers = iter(["x", "99", "1"])
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: next(answers))
    assert choose(Console(record=True), "選一個", [("甲", "a"), ("乙", "b")]) == "a"


def test_choose_empty_rows_returns_none(monkeypatch):
    from client.ui import choose
    from rich.console import Console
    assert choose(Console(record=True), "空", []) is None


def test_choose_many_parses_multiple_numbers(monkeypatch):
    from client.ui import choose_many
    from rich.console import Console
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: "1, 3")
    rows = [("甲", "a"), ("乙", "b"), ("丙", "c")]
    assert choose_many(Console(record=True), "選幾個", rows) == ["a", "c"]


def test_choose_many_blank_means_auto(monkeypatch):
    from client.ui import choose_many
    from rich.console import Console
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: "  ")
    assert choose_many(Console(record=True), "選幾個", [("甲", "a")]) == []


def test_choose_many_reprompts_on_invalid(monkeypatch):
    from client.ui import choose_many
    from rich.console import Console
    answers = iter(["9", "2 1"])
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: next(answers))
    rows = [("甲", "a"), ("乙", "b")]
    assert choose_many(Console(record=True), "選幾個", rows) == ["b", "a"]


def test_do_hunt_passes_selected_monster_ids(monkeypatch):
    from client import app
    from rich.console import Console

    class _HuntApi:
        def __init__(self):
            self.calls = []

        def list_characters(self):
            return [{"id": 1, "base_level": 20, "name": "阿獵"}]

        def hunt_start(self, map_id, monster_ids=None):
            self.calls.append((map_id, monster_ids))

    monkeypatch.setattr(app, "_choose", lambda *a, **k: "prontera_east_gate")
    monkeypatch.setattr(app, "_choose_many", lambda *a, **k: ["mad_bunny", "chick"])
    monkeypatch.setattr(app, "watch_hunt", lambda *a, **k: None)
    rec = _HuntApi()
    app._do_hunt(rec, {"id": 1, "base_level": 20, "name": "阿獵"}, Console(record=True))
    assert rec.calls == [("prontera_east_gate", ["mad_bunny", "chick"])]


def test_do_hunt_blank_selection_is_auto(monkeypatch):
    from client import app
    from rich.console import Console

    class _HuntApi:
        def __init__(self):
            self.calls = []

        def list_characters(self):
            return [{"id": 1, "base_level": 20, "name": "阿獵"}]

        def hunt_start(self, map_id, monster_ids=None):
            self.calls.append((map_id, monster_ids))

    monkeypatch.setattr(app, "_choose", lambda *a, **k: "prontera_east_gate")
    monkeypatch.setattr(app, "_choose_many", lambda *a, **k: [])
    monkeypatch.setattr(app, "watch_hunt", lambda *a, **k: None)
    rec = _HuntApi()
    app._do_hunt(rec, {"id": 1, "base_level": 20, "name": "阿獵"}, Console(record=True))
    assert rec.calls == [("prontera_east_gate", [])]


def test_do_hunt_cancel_on_map_back(monkeypatch):
    from client import app
    from rich.console import Console

    class _HuntApi:
        def __init__(self):
            self.calls = []

        def list_characters(self):
            return [{"id": 1, "base_level": 20, "name": "阿獵"}]

        def hunt_start(self, *a, **k):
            self.calls.append(a)

    monkeypatch.setattr(app, "_choose", lambda *a, **k: None)
    called = []
    monkeypatch.setattr(app, "_choose_many", lambda *a, **k: called.append(1) or [])
    monkeypatch.setattr(app, "watch_hunt", lambda *a, **k: None)
    rec = _HuntApi()
    app._do_hunt(rec, {"id": 1, "base_level": 20, "name": "阿獵"}, Console(record=True))
    assert rec.calls == [] and called == []


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
    from client import menus, ui
    from rich.console import Console
    # ui.choose: 買(1) → 商品第一項(1)
    answers = iter(["1", "1"])
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: next(answers)))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 5))
    rec = _RecApi()
    menus.shop_menu(rec, {"id": 1}, Console(record=True))
    assert ("buy", "red_potion", 5) in rec.calls


def test_shop_menu_shows_chinese_sell_name_and_price(monkeypatch):
    from client import menus
    from rich.console import Console

    class SellApi:
        def __init__(self):
            self.calls = []

        def shop(self):
            return {"items": [], "equipment": []}

        def inventory(self, cid):
            return {"items": {"red_potion": 3}, "equipment": []}

        def sell(self, **kwargs):
            self.calls.append(kwargs)
            return {"ok": True, "gained": 50}

    answers = iter(["2", "1"])
    monkeypatch.setattr("client.ui.Prompt.ask", lambda *a, **k: next(answers))
    monkeypatch.setattr(menus.IntPrompt, "ask", staticmethod(lambda *a, **k: 2))
    api = SellApi()
    con = Console(record=True, width=100)
    menus.shop_menu(api, {"id": 1}, con)
    out = con.export_text()
    assert "紅色藥水" in out
    assert "單價 25z" in out
    assert "可得 75z" in out
    assert "獲得 50 Zeny" in out
    assert api.calls == [{"item_id": "red_potion", "qty": 2}]


def test_refine_menu_calls_refine(monkeypatch):
    from client import menus, ui
    from rich.console import Console
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: "1"))
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
    from client import menus, ui
    from rich.console import Console
    # ui.choose: 選 MVP(1) → 血線 15%(1)
    answers = iter(["1", "1"])
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: next(answers)))
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
    from client import menus, ui
    from rich.console import Console
    # ui.choose 選「建立新公會」(1)；menus.Prompt.ask 問公會名稱
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: "1"))
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "波利獵人團"))
    rec = _SocialApi(mine=None)
    menus.guild_menu(rec, {"id": 1}, Console(record=True))
    assert ("guild_create", "波利獵人團") in rec.calls


def test_guild_menu_join(monkeypatch):
    from client import menus, ui
    from rich.console import Console
    # rows: 1=建立新公會, 2=波利團 → 選 2
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: "2"))
    rec = _SocialApi(mine=None)
    menus.guild_menu(rec, {"id": 1}, Console(record=True))
    assert ("guild_join", 1) in rec.calls


def test_trade_menu_opens_new_then_cancel(monkeypatch):
    from client import menus, ui
    from rich.console import Console
    # ui.choose: 交易選單選「開新交易」(1)；_trade_screen 動作選「取消交易」
    ui_answers = iter(["1", "3"])
    monkeypatch.setattr(ui.Prompt, "ask", staticmethod(lambda *a, **k: next(ui_answers)))
    monkeypatch.setattr(menus.Prompt, "ask", staticmethod(lambda *a, **k: "bob"))
    rec = _SocialApi()
    menus.trade_menu(rec, {"id": 1}, Console(record=True))
    assert ("trade_offer", "bob") in rec.calls
    assert ("trade_cancel", 7) in rec.calls


class _ScreenApi:
    def __init__(self, hunt=None, chat=None):
        self._hunt = hunt
        self._chat = list(chat or [])
        self.mult_calls = []

    def list_characters(self):
        return [{"id": 1, "name": "阿獵", "base_level": 3, "job_id": "novice",
                 "location_map": "prontera_east_gate"}]

    def sheet(self, cid):
        return {"max_hp": 50, "max_sp": 12, "hunt_hp": 40, "hunt_sp": 10}

    def hunt_status(self):
        from client.api import ApiError
        if self._hunt is None:
            raise ApiError(409, "沒有在掛機")
        return self._hunt

    def chat_since(self, channel, after=0):
        if channel != "world":
            return []
        return [m for m in self._chat if m["id"] > after]

    def guild_mine(self):
        return None

    def me(self):
        return {"account_id": 1, "username": "u", "role": "player", "is_gm": False}

    def admin_settings(self):
        return {"experience_multiplier": 1.0, "drop_multiplier": 1.0,
                "settle_floor_seconds": 15.0, "huntable_win_rate": 0.6}

    def admin_set_multipliers(self, experience, drop):
        self.mult_calls.append((experience, drop))


def _state():
    return {"is_gm": False, "chat": [], "chat_last": {}, "chat_seeded": False,
            "guild_id": None}


def test_render_screen_shows_hunt_panel_when_hunting(monkeypatch):
    from client import app
    from rich.console import Console
    api = _ScreenApi(hunt={"monster_name": "綠棉蟲", "kills": 5, "base_exp": 12,
                           "job_exp": 6, "zeny": 4, "effective_seconds": 90,
                           "retreated": False})
    con = Console(record=True, width=100)
    app._render_screen(con, api, {"id": 1, "name": "阿獵"}, None, _state())
    out = con.export_text()
    assert "掛機狀態" in out and "綠棉蟲" in out


def test_render_screen_shows_recent_chat(monkeypatch):
    from client import app
    from rich.console import Console
    api = _ScreenApi(chat=[{"id": 1, "character_name": "路人", "text": "哈囉大家"}])
    con = Console(record=True, width=100)
    st = _state()
    app._render_screen(con, api, {"id": 1, "name": "阿獵"}, None, st)
    out = con.export_text()
    assert "哈囉大家" in out and "路人" in out


def test_render_screen_gm_entry_only_for_gm():
    from client import app
    from rich.console import Console
    api = _ScreenApi()
    con = Console(record=True, width=100)
    st = _state()
    app._render_screen(con, api, {"id": 1, "name": "阿獵"}, None, st)
    assert "GM管理" not in con.export_text()
    st["is_gm"] = True
    con2 = Console(record=True, width=100)
    app._render_screen(con2, api, {"id": 1, "name": "阿獵"}, None, st)
    assert "GM管理" in con2.export_text()


def test_refresh_chat_seeds_then_increments():
    from client import app
    msgs = [{"id": i, "character_name": "A", "text": f"m{i}"} for i in range(1, 13)]
    api = _ScreenApi(chat=msgs)
    st = _state()
    app._refresh_chat(api, st)
    # 第一次只取最後 8 條
    assert len(st["chat"]) == 8
    assert st["chat_last"]["world"] == 12
    # 之後新增一條，只帶新的
    api._chat.append({"id": 13, "character_name": "A", "text": "m13"})
    app._refresh_chat(api, st)
    assert len(st["chat"]) == 9


def test_gm_menu_sets_multipliers(monkeypatch):
    from client import menus
    from rich.console import Console
    api = _ScreenApi()
    actions = iter(["mult", None])  # 選倍率一次，第二圈返回
    monkeypatch.setattr(menus, "choose", lambda *a, **k: next(actions))
    monkeypatch.setattr(menus.Prompt, "ask",
                        staticmethod(lambda *a, **k: next(iter(["2"]))
                                     if "經驗" in a[0] else "3"))
    menus.gm_menu(api, {"id": 1}, Console(record=True))
    assert api.mult_calls == [(2.0, 3.0)]


def test_render_screen_survives_markup_in_chat():
    from client import app
    from rich.console import Console
    api = _ScreenApi(chat=[{"id": 1, "character_name": "壞[人]",
                            "text": "哈囉[/]大家[bold]注意"}])
    con = Console(record=True, width=100)
    app._render_screen(con, api, {"id": 1, "name": "阿獵"}, None, _state())
    out = con.export_text()
    assert "哈囉" in out and "大家" in out  # 沒 crash，字有出來


def test_chat_mode_single_shot_sends_and_returns(monkeypatch):
    from client import chat as chatmod
    from rich.console import Console

    class _ChatApi:
        def __init__(self):
            self.posted = []
        def chat_since(self, channel, after=0):
            return [{"id": 1, "character_name": "路人", "text": "hi"}]
        def chat_post(self, channel, text):
            self.posted.append((channel, text))

    api = _ChatApi()
    monkeypatch.setattr(chatmod.Prompt, "ask", staticmethod(lambda *a, **k: "大家好"))
    chatmod.chat_mode(api, Console(record=True), has_guild=False)
    assert api.posted == [("world", "大家好")]


def test_chat_mode_blank_does_not_send(monkeypatch):
    from client import chat as chatmod
    from rich.console import Console

    class _ChatApi:
        def __init__(self):
            self.posted = []
        def chat_since(self, channel, after=0):
            return []
        def chat_post(self, channel, text):
            self.posted.append((channel, text))

    api = _ChatApi()
    monkeypatch.setattr(chatmod.Prompt, "ask", staticmethod(lambda *a, **k: "   "))
    chatmod.chat_mode(api, Console(record=True), has_guild=False)
    assert api.posted == []
