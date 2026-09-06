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


def test_watch_stops_on_retreat(monkeypatch):
    import time
    monkeypatch.setattr(builtins, "input", lambda: time.sleep(10))
    api = _FakeApi([
        {"events": [{"kind": "kill_batch", "monster_name": "波利", "count": 3,
                     "base_exp": 6, "job_exp": 3, "zeny": 15}], "retreated": False},
        {"events": [], "retreated": True, "retreat_reason": "補品用盡",
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
    import time
    monkeypatch.setattr(builtins, "input", lambda: time.sleep(10))

    class _Boom:
        def hunt_status(self):
            raise RuntimeError("nope")

    con = Console(record=True, width=80)
    watch_hunt(_Boom(), con, poll_seconds=0.01)
    assert "結算失敗" in con.export_text()


def test_watch_handles_no_active_hunt_as_normal_state(monkeypatch):
    import time
    monkeypatch.setattr(builtins, "input", lambda: time.sleep(10))

    class _NoHunt:
        def hunt_status(self):
            raise ApiError(409, "目前沒有正在掛機")

    con = Console(record=True, width=80)
    watch_hunt(_NoHunt(), con, poll_seconds=0.01)
    out = con.export_text()
    assert "目前沒有正在掛機" in out
    assert "結算失敗" not in out
