import builtins

from rich.console import Console

from client.api import ApiError
from client import watch as watch_mod
from client.watch import watch_hunt


class _FakeApi:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.calls = 0

    def hunt_status(self):
        self.calls += 1
        return self._statuses[min(self.calls - 1, len(self._statuses) - 1)]


def _stepping_clock():
    c = [0.0]

    def inner():
        c[0] += 1.0
        return c[0]

    return inner


def _block_input(monkeypatch):
    import time
    monkeypatch.setattr(builtins, "input", lambda: time.sleep(10))


def test_watch_stops_on_retreat(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    api = _FakeApi([
        {"batch_id": "b1",
         "events": [{"kind": "kill_batch", "monster_name": "波利", "count": 3,
                     "base_exp": 6, "job_exp": 3, "zeny": 15}], "retreated": False},
        {"batch_id": "b1", "events": [], "retreated": True,
         "retreat_reason": "補品用盡",
         "kills": 3, "base_exp": 6, "job_exp": 3, "zeny": 15, "effective_seconds": 30},
    ])
    con = Console(record=True, width=80)
    watch_hunt(api, con, poll_seconds=0.01)
    out = con.export_text()
    assert "波利" in out
    assert "已撤退" in out


def test_watch_stops_on_enter(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda: "")
    api = _FakeApi([{"events": [], "retreated": False}])
    con = Console(record=True, width=80)
    watch_hunt(api, con, poll_seconds=5.0)
    assert "停止觀看" in con.export_text()


def test_watch_handles_api_error(monkeypatch):
    _block_input(monkeypatch)

    class _Boom:
        def hunt_status(self):
            raise RuntimeError("nope")

    con = Console(record=True, width=80)
    watch_hunt(_Boom(), con, poll_seconds=0.01)
    assert "出錯" in con.export_text()


def test_watch_handles_no_active_hunt_as_normal_state(monkeypatch):
    _block_input(monkeypatch)

    class _NoHunt:
        def hunt_status(self):
            raise ApiError(409, "目前沒有正在掛機")

    con = Console(record=True, width=80)
    watch_hunt(_NoHunt(), con, poll_seconds=0.01)
    out = con.export_text()
    assert "目前沒有正在掛機" in out
    assert "結算失敗" not in out


def _attack_batch(n, batch_id="b1", retreated=False):
    return {
        "batch_id": batch_id,
        "retreated": retreated,
        "events": [{"kind": "attack", "actor": "T", "target": "王",
                    "damage": 1000 + i, "crit": False, "hit": True}
                   for i in range(n)],
    }


def test_watch_small_batch_drips_one_per_second(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    # 5 事件的小批次：第 2 次輪詢（撤退）前只吐得出一部分
    api = _FakeApi([
        _attack_batch(5),
        {"batch_id": "b1", "events": [], "retreated": True,
         "retreat_reason": "補品用盡", "kills": 0, "base_exp": 0,
         "job_exp": 0, "zeny": 0, "effective_seconds": 2},
    ])
    con = Console(record=True, width=120)
    watch_hunt(api, con, poll_seconds=0.01)
    out = con.export_text()
    shown = sum(1 for i in range(5) if str(1000 + i) in out)
    assert 0 < shown < 5


def test_watch_big_batch_dumped_immediately(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    # 25 事件的大批次：不逐播，第一次輪詢就全進 history（視窗顯示最後 10 行）
    api = _FakeApi([
        _attack_batch(25),
        {"batch_id": "b1", "events": [], "retreated": True,
         "retreat_reason": "補品用盡", "kills": 0, "base_exp": 0,
         "job_exp": 0, "zeny": 0, "effective_seconds": 2},
    ])
    con = Console(record=True, width=120)
    watch_hunt(api, con, poll_seconds=0.01)
    out = con.export_text()
    assert str(1000 + 24) in out  # 尾段（最後 10 行內）第一輪就看得到


def test_watch_offline_batch_shows_summary(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    api = _FakeApi([
        {"batch_id": "b1", "retreated": False, "offline": True,
         "kills": 42, "base_exp": 500, "job_exp": 250, "zeny": 99,
         "events": [{"kind": "kill_batch", "monster_name": "波利", "count": 42,
                     "base_exp": 500, "job_exp": 250, "zeny": 99}]},
        {"batch_id": "b1", "events": [], "retreated": True,
         "retreat_reason": "補品用盡", "kills": 42, "base_exp": 500,
         "job_exp": 250, "zeny": 99, "effective_seconds": 9000},
    ])
    con = Console(record=True, width=120)
    watch_hunt(api, con, poll_seconds=0.01)
    out = con.export_text()
    assert "離線結算" in out


def test_watch_ignores_repeated_same_batch_id(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    same = {"batch_id": "b1", "retreated": False,
            "events": [{"kind": "attack", "actor": "T", "target": "王",
                        "damage": d, "crit": False, "hit": True}
                       for d in (111, 222, 333)]}
    statuses = [dict(same) for _ in range(10)]
    statuses.append({"batch_id": "b1", "events": [], "retreated": True,
                     "retreat_reason": "補品用盡", "kills": 0, "base_exp": 0,
                     "job_exp": 0, "zeny": 0, "effective_seconds": 10})
    api = _FakeApi(statuses)
    con = Console(record=True, width=120)
    watch_hunt(api, con, poll_seconds=0.001)
    out = con.export_text()
    # 同一 batch_id 只塞一次，每個傷害數字最多出現一次
    for d in ("111", "222", "333"):
        assert out.count(d) <= 1


def test_watch_new_batch_id_adds_more(monkeypatch):
    _block_input(monkeypatch)
    monkeypatch.setattr(watch_mod.time, "monotonic", _stepping_clock())
    statuses = [
        {"batch_id": "b1", "retreated": False,
         "events": [{"kind": "attack", "actor": "T", "target": "王",
                     "damage": 111, "crit": False, "hit": True}]},
        {"batch_id": "b1", "retreated": False,
         "events": [{"kind": "attack", "actor": "T", "target": "王",
                     "damage": 111, "crit": False, "hit": True}]},
        {"batch_id": "b2", "retreated": False,
         "events": [{"kind": "attack", "actor": "T", "target": "王",
                     "damage": 222, "crit": False, "hit": True}]},
        {"batch_id": "b2", "retreated": False,
         "events": [{"kind": "attack", "actor": "T", "target": "王",
                     "damage": 222, "crit": False, "hit": True}]},
        {"batch_id": "b2", "events": [], "retreated": True,
         "retreat_reason": "補品用盡", "kills": 0, "base_exp": 0,
         "job_exp": 0, "zeny": 0, "effective_seconds": 5},
    ]
    api = _FakeApi(statuses)
    con = Console(record=True, width=120)
    watch_hunt(api, con, poll_seconds=0.001)
    out = con.export_text()
    assert "111" in out and "222" in out
