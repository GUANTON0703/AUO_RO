import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from client.api import ApiClient, ApiError
from client.auth_flow import ensure_logged_in, select_or_create_character
from client.config import SessionStore
from client.chat import chat_mode
from client.menus import (
    equip_menu,
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
)
from client.render import (
    event_lines,
    hunt_summary,
    inventory_table,
    newbie_hint_panel,
    status_panel,
)
from client.ui import choose as _choose
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
    ("h", "掛機"), ("v", "查看掛機"), ("stop", "停止掛機"),
    ("stats", "加點"), ("skills", "學技能"), ("equip", "裝備"),
    ("refine", "精煉"), ("socket", "鑲卡"), ("shop", "商店"),
    ("storage", "倉庫"), ("job", "轉職"), ("mvp", "MVP 王"),
    ("rank", "排行榜"), ("trade", "交易"), ("guild", "公會"), ("chat", "聊天"),
    ("i", "背包"), ("s", "狀態"), ("help", "說明"), ("q", "離開"),
]

_NO_PAUSE = {"h", "hunt", "v", "watch", "q", "quit", "exit"}


def _render_screen(console: Console, api: ApiClient, character: dict, last_output) -> None:
    console.clear()
    console.print(status_panel(_merge_sheet(api, _current_character(api, character))))
    if last_output:
        console.print(last_output)
    cols = "　".join(f"[cyan]{k}[/cyan] {label}" for k, label in _MENU)
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
    monster_id = _choose(
        console,
        "選擇目標怪物",
        [(f"{_content.get_monster(mid).name}（Lv {_content.get_monster(mid).level}）", mid)
         for mid in map_def.monster_ids],
    )
    try:
        api.hunt_start(map_id, monster_id or None)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    watch_hunt(api, console, render_status=lambda _status: _render_screen(
        console, api, character, None
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
        "guild": guild_menu,
    }

    last_output = "[bold green]歡迎回來，" + character["name"] + "！[/bold green] 輸入指令代號或直接打字。"
    while True:
        _render_screen(console, api, character, last_output)
        try:
            cmd = Prompt.ask("[cyan]>[/cyan]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        try:
            if cmd in ("q", "quit", "exit"):
                break
            elif cmd in ("h", "hunt"):
                _do_hunt(api, character, console)
            elif cmd in ("v", "watch"):
                watch_hunt(api, console, render_status=lambda _status: _render_screen(
                    console, api, character, None
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
            elif cmd == "help":
                console.print(_HELP)
            else:
                console.print("未知指令，輸入 help。")
        except ApiError as exc:
            console.print(f"[red]錯誤：{exc.detail}[/red]")

        last_output = None
        if cmd not in _NO_PAUSE:
            try:
                Prompt.ask("\n[dim]按 Enter 回主選單[/dim]", default="")
            except (EOFError, KeyboardInterrupt):
                break

    saved = store.load() or {}
    store.save(server_url=server_url, token=api.token, username=saved.get("username"))
    console.print("再見。")
