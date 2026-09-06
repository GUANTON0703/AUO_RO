"""手動試玩檢查：in-process TestClient 跑一輪客戶端改版重點流程。

    uv run python scripts/revamp_check.py
"""
import tempfile
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from rich.console import Console

from client.api import ApiClient
from client.app import _merge_sheet, _render_screen
from client.menus import stats_menu
from client.render import retreat_advice
from client.terminal import prepare_windows_console
from server.app import create_app
from server.db import connection


def _rewind(cid: int, seconds: int) -> None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT hunt_last_settled_at FROM characters WHERE id = ?", (cid,)
        ).fetchone()
        new = (datetime.fromisoformat(row["hunt_last_settled_at"])
               - timedelta(seconds=seconds)).isoformat()
        conn.execute(
            "UPDATE characters SET hunt_last_settled_at = ?, hunt_started_at = ? WHERE id = ?",
            (new, new, cid),
        )


def main() -> None:
    prepare_windows_console()
    console = Console()
    db = tempfile.mktemp(suffix=".db")
    connection.configure(db)
    connection.init_db()
    from server.auth import invites

    code = invites.create_invite()
    api = ApiClient(TestClient(create_app()))
    api.register(code, "hero", "password123")
    api.login("hero", "password123")
    ch = api.create_character("小勇者")
    cid = ch["id"]

    console.rule("1) _render_screen（置頂狀態）")
    _state = {"is_gm": False, "chat": [], "chat_last": {}, "chat_seeded": False,
              "guild_id": None}
    _render_screen(console, api, ch, "（上一個動作的輸出會出現在這）", _state)

    console.rule("2) stats_menu 配點器（選 str 3 次再完成）")
    answers = iter(["1", "1", "1", "0"])
    import client.menus as m
    _orig = m.Prompt.ask
    m.Prompt.ask = staticmethod(lambda *a, **k: next(answers))
    try:
        fresh = next(r for r in api.list_characters() if r["id"] == cid)
        stats_menu(api, fresh, console)
    finally:
        m.Prompt.ask = _orig

    console.rule("3) 加點後掛機東門村郊 + rewind 40 秒看逐回合事件")
    fresh = next(r for r in api.list_characters() if r["id"] == cid)
    api.allocate_stats(cid, {"str": 5, "vit": 3, "agi": 3})
    api.hunt_start("prontera_east_gate", ["green_cotton_worm"])
    _rewind(cid, 40)
    status = api.hunt_status()
    kinds = [e.get("kind") for e in status.get("events", [])]
    console.print(f"事件種類：{sorted(set(kinds))}")
    console.print(f"attack/kill 出現：{'attack' in kinds}/{'kill' in kinds}  "
                  f"kill_batch：{'kill_batch' in kinds}")
    api.hunt_stop()

    console.rule("4) 菜雞硬指定強怪 rewind 3h → 撤退 + 建議")
    api2 = ApiClient(api._http)
    api2.register(invites.create_invite(), "weak", "password123")
    api2.login("weak", "password123")
    w = api2.create_character("菜雞")
    # 全 1 新手自動模式會被擋下；指定強怪硬掛才會演到「撤退」
    api2.hunt_start("prontera_east_gate", ["yoyo_monkey"])
    _rewind(w["id"], 3 * 3600)
    st = api2.hunt_stop()
    console.print(f"retreated={st.get('retreated')}  reason={st.get('retreat_reason')!r}")
    console.print(f"建議：{retreat_advice(st.get('retreat_reason', ''))}")


if __name__ == "__main__":
    main()
