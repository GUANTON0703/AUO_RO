import time

import httpx
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from client.api import ApiClient, ApiError
from client.auth_flow import ensure_logged_in, select_or_create_character
from client.config import SessionStore
from client.chat import chat_mode
from client.menus import (
    equip_menu,
    content_menu,
    gm_menu,
    guild_menu,
    jobchange_menu,
    mvp_menu,
    rank_menu,
    refine_menu,
    shop_menu,
    skills_menu,
    socket_menu,
    stats_menu,
    storage_menu,
    trade_menu,
    strategy_menu,
)
from client.render import (
    event_lines,
    hunt_status_panel,
    hunt_summary,
    inventory_table,
    newbie_hint_panel,
    status_panel,
)
from client.ui import choose as _choose, choose_many as _choose_many
from client.watch import watch_hunt
from server.content import load_content

_content = load_content()

_HELP = """指令：
  h / hunt    選地圖掛機（進觀看模式，Enter 離開觀看）
  stop        停止掛機並結算
  s / status  顯示角色狀態
  i / inv     背包
  stats       加屬性點
  skills      學技能
  equip       裝備 / 卸下
  refine      精煉
  socket      鑲卡
  shop        商店買賣
  storage     倉庫存取
  job         轉職
  mvp         挑戰 MVP 王
  rank        排行榜
  trade       面對面交易
  guild       公會
  chat        世界／公會聊天（空行離開）
  help        本說明
  q / quit    離開
"""


_MENU = [
    ("h", "掛機"), ("v", "查看"), ("x", "停止"), ("a", "加點"),
    ("k", "技能"), ("e", "裝備"), ("r", "精煉"), ("o", "鑲卡"),
    ("b", "商店"), ("w", "倉庫"), ("j", "轉職"), ("m", "MVP"),
    ("l", "排行"), ("t", "交易"), ("g", "公會"), ("c", "聊天"),
    ("i", "背包"), ("d", "資料"), ("u", "掛機設定"), ("s", "狀態"),
    ("?", "說明"), ("q", "離開"),
]

_ALIASES = {
    "x": "stop", "a": "stats", "k": "skills", "e": "equip", "r": "refine",
    "o": "socket", "b": "shop", "w": "storage", "j": "job", "m": "mvp",
    "l": "rank", "t": "trade", "g": "guild", "c": "chat", "?": "help",
    "d": "content", "u": "strategy",
    "hunt": "h", "watch": "v", "status": "s", "inv": "i", "quit": "q", "exit": "q",
}

_NO_PAUSE = {"h", "hunt", "v", "watch", "c", "chat", "q", "quit", "exit"}


def _try_hunt_status(api: ApiClient) -> dict | None:
    try:
        return api.hunt_status()
    except Exception:
        return None


def _refresh_chat(api: ApiClient, state: dict) -> None:
    channels = ["world"]
    if state.get("guild_id"):
        channels.append(f"guild:{state['guild_id']}")
    first = not state.get("chat_seeded")
    for ch in channels:
        try:
            msgs = api.chat_since(ch, state["chat_last"].get(ch, 0)) or []
        except Exception:
            continue
        if first:
            msgs = msgs[-8:]
        for m in msgs:
            state["chat_last"][ch] = m["id"]
            tag = "" if ch == "world" else "[magenta][公會][/magenta] "
            name = escape(str(m.get("character_name", "?")))
            text = escape(str(m.get("text", "")))
            state["chat"].append(
                Text.from_markup(f"{tag}[cyan]{name}[/cyan]：{text}")
            )
    del state["chat"][:-40]
    state["chat_seeded"] = True


def _render_screen(console: Console, api: ApiClient, character: dict,
                   last_output, state: dict) -> None:
    console.clear()
    char_panel = status_panel(_merge_sheet(api, _current_character(api, character)))
    hunt = _try_hunt_status(api)
    if hunt and not hunt.get("retreated"):
        # 掛機時間本地補間：伺服器回的秒數變了就重新對時，沒變就自己往前跑，
        # 這樣每次重繪畫面都看得到時間在動、不會像停住了
        secs = float(hunt.get("effective_seconds", 0) or 0)
        if secs != state.get("hunt_secs"):
            state["hunt_secs"] = secs
            state["hunt_secs_at"] = time.monotonic()
        shown = state.get("hunt_secs", 0) + (time.monotonic() - state.get("hunt_secs_at", time.monotonic()))
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(char_panel, hunt_status_panel(hunt, shown))
        console.print(grid)
    else:
        state["hunt_secs"] = None
        console.print(char_panel)

    _refresh_chat(api, state)
    if state["chat"]:
        console.print(Panel(Group(*state["chat"][-8:]), title="聊天（c 進入）", expand=False))

    if last_output:
        console.print(last_output)
    entries = _MENU + [("gm", "GM管理")] if state.get("is_gm") else _MENU
    cols = "　".join(f"[cyan]{k}[/cyan] {label}" for k, label in entries)
    console.print(Panel(cols, title="指令", expand=False))


def _merge_sheet(api: ApiClient, character: dict) -> dict:
    merged = dict(character)
    try:
        sheet = api.sheet(character["id"])
        merged["max_hp"] = sheet["max_hp"]
        merged["max_sp"] = sheet["max_sp"]
        merged["hp"] = sheet["hunt_hp"]
        merged["sp"] = sheet["hunt_sp"]
    except ApiError:
        pass
    return merged


def _current_character(api: ApiClient, character: dict) -> dict:
    try:
        for row in api.list_characters():
            if row["id"] == character["id"]:
                return row
    except ApiError:
        pass
    return character


def _show_status(api: ApiClient, character: dict, console: Console) -> dict:
    fresh = _current_character(api, character)
    console.print(status_panel(_merge_sheet(api, fresh)))
    return fresh


def _do_hunt(api: ApiClient, character: dict, console: Console) -> None:
    fresh = _current_character(api, character)
    bl = fresh.get("base_level", 1)
    maps = [
        m for m in _content.maps.values()
        if bl >= getattr(m, "unlock_base_level", 1)
    ]
    if not maps:
        console.print("[yellow]還沒有解鎖的地圖。[/yellow]")
        return
    map_id = _choose(
        console,
        "選擇狩獵地圖",
        [(f"{m.name}（解鎖 Lv {getattr(m, 'unlock_base_level', 1)}）", m.id)
         for m in maps],
    )
    if map_id is None:
        return
    map_def = _content.maps[map_id]
    monster_rows = [
        (f"{mon.name}（Lv {mon.level}）", mid)
        for mid in map_def.monster_ids
        for mon in [_content.get_monster(mid)]
    ]
    monster_ids = _choose_many(
        console,
        "要打哪幾隻怪？留空 = 自動選好打的，可多選（例如 1,3）",
        monster_rows,
    )
    try:
        api.hunt_start(map_id, monster_ids)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    watch_hunt(api, console, render_status=lambda _status: status_panel(
        _merge_sheet(api, _current_character(api, character))
    ))


def _do_stop(api: ApiClient, console: Console) -> None:
    try:
        summary = api.hunt_stop()
        console.print(hunt_summary(summary))
    except ApiError as exc:
        if exc.status == 409:
            console.print("[yellow]目前沒有在掛機。[/yellow]")
        else:
            console.print(f"[red]{exc.detail}[/red]")


def run(server_url: str) -> None:
    from client.terminal import make_console, prepare_windows_console

    prepare_windows_console()
    console = make_console()
    store = SessionStore()
    http = httpx.Client(base_url=server_url, timeout=30.0)
    api = ApiClient(http)

    try:
        ensure_logged_in(api, store, server_url)
    except (ApiError, KeyboardInterrupt) as exc:
        console.print(f"[red]登入失敗：{exc}[/red]")
        return

    character = select_or_create_character(api)

    fresh = _current_character(api, character)
    if sum(fresh.get(f"stat_{k}", 1) for k in
           ("str", "agi", "vit", "int", "dex", "luk")) <= 8:
        console.print(newbie_hint_panel())
        try:
            Prompt.ask("\n[dim]按 Enter 開始[/dim]", default="")
        except (EOFError, KeyboardInterrupt):
            return

    menus = {
        "stats": stats_menu, "skills": skills_menu, "equip": equip_menu,
        "refine": refine_menu, "socket": socket_menu, "shop": shop_menu,
        "storage": storage_menu, "job": jobchange_menu,
        "mvp": mvp_menu, "rank": rank_menu, "trade": trade_menu,
        "guild": guild_menu, "content": content_menu, "strategy": strategy_menu,
    }

    state = {"is_gm": False, "chat": [], "chat_last": {}, "chat_seeded": False,
             "guild_id": None}
    try:
        state["is_gm"] = bool((api.me() or {}).get("is_gm"))
    except ApiError:
        pass
    try:
        g = api.guild_mine()
        state["guild_id"] = g["id"] if g else None
    except ApiError:
        pass
    if state["is_gm"]:
        menus["gm"] = gm_menu

    last_output = "[bold green]歡迎回來，" + character["name"] + "！[/bold green] 輸入指令代號或直接打字。"
    while True:
        try:
            _render_screen(console, api, character, last_output, state)
        except Exception as exc:
            import traceback
            console.print(f"[red]畫面繪製出錯：{exc}[/red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        try:
            cmd = Prompt.ask("[cyan]>[/cyan]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        cmd = _ALIASES.get(cmd, cmd)
        try:
            if cmd in ("q", "quit", "exit"):
                break
            elif cmd in ("h", "hunt"):
                _do_hunt(api, character, console)
            elif cmd in ("v", "watch"):
                watch_hunt(api, console, render_status=lambda _status: status_panel(
                    _merge_sheet(api, _current_character(api, character))
                ))
            elif cmd == "stop":
                _do_stop(api, console)
            elif cmd in ("s", "status"):
                character = _show_status(api, character, console)
            elif cmd in ("i", "inv"):
                console.print(inventory_table(api.inventory(character["id"])))
            elif cmd == "chat":
                has_guild = False
                try:
                    has_guild = api.guild_mine() is not None
                except ApiError:
                    pass
                chat_mode(api, console, has_guild)
            elif cmd in menus:
                character = _current_character(api, character)
                menus[cmd](api, character, console)
                if cmd == "guild":
                    try:
                        g = api.guild_mine()
                        state["guild_id"] = g["id"] if g else None
                    except ApiError:
                        pass
            elif cmd == "help":
                console.print(_HELP)
            else:
                console.print("未知指令，輸入 help。")
        except ApiError as exc:
            console.print(f"[red]錯誤：{exc.detail}[/red]")
        except Exception as exc:
            import traceback
            console.print(f"[red]指令「{cmd}」出錯：{exc}[/red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

        last_output = None
        if cmd not in _NO_PAUSE:
            try:
                Prompt.ask("\n[dim]按 Enter 回主選單[/dim]", default="")
            except (EOFError, KeyboardInterrupt):
                break

    saved = store.load() or {}
    store.save(server_url=server_url, token=api.token, username=saved.get("username"))
    console.print("再見。")
