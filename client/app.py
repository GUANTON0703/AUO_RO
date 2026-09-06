import httpx
from rich.console import Console
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
from client.render import event_lines, hunt_summary, inventory_table, status_panel
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
    for m in maps:
        console.print(f"  {m.id}　{m.name}（解鎖 Lv {getattr(m, 'unlock_base_level', 1)}）")
    map_id = Prompt.ask("去哪張圖（map_id）", choices=[m.id for m in maps])
    map_def = _content.maps[map_id]
    for mid in map_def.monster_ids:
        mon = _content.get_monster(mid)
        console.print(f"  {mid}　{mon.name}　Lv {mon.level}")
    monster_id = Prompt.ask("打哪種怪（monster_id，留空自動選）", default="")
    try:
        api.hunt_start(map_id, monster_id or None)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    watch_hunt(api, console)


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
    console.print(f"[bold green]歡迎回來，{character['name']}！[/bold green]")
    _show_status(api, character, console)
    console.print("輸入 help 看指令。")

    menus = {
        "stats": stats_menu, "skills": skills_menu, "equip": equip_menu,
        "refine": refine_menu, "socket": socket_menu, "shop": shop_menu,
        "storage": storage_menu, "job": jobchange_menu,
        "mvp": mvp_menu, "rank": rank_menu, "trade": trade_menu,
        "guild": guild_menu,
    }

    while True:
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

    saved = store.load() or {}
    store.save(server_url=server_url, token=api.token, username=saved.get("username"))
    console.print("再見。")
