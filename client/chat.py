from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

from client.api import ApiClient, ApiError


def chat_mode(
    api: ApiClient,
    console: Console | None = None,
    has_guild: bool = False,
) -> None:
    """單發：印出最近訊息，讓你打一句話送出就回主選單。直接 Enter = 只看不送。
    收訊息靠主畫面常駐的聊天面板，這裡不做輪詢。"""
    console = console or Console()

    channel = "world"
    if has_guild:
        try:
            mine = api.guild_mine()
        except ApiError:
            mine = None
        if mine:
            pick = Prompt.ask("送到 [w] 世界 / [g] 公會", choices=["w", "g"], default="w")
            if pick == "g":
                channel = f"guild:{mine['id']}"

    try:
        msgs = api.chat_since(channel, 0) or []
    except ApiError:
        msgs = []
    for m in msgs[-12:]:
        name = escape(str(m.get("character_name", "?")))
        text = escape(str(m.get("text", "")))
        console.print(f"[cyan]{name}[/cyan]：{text}")

    try:
        line = Prompt.ask("[dim]說一句（直接 Enter 離開）[/dim]", default="").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not line:
        return
    try:
        api.chat_post(channel, line)
        console.print("[green]已送出[/green]")
    except ApiError as exc:
        console.print(f"[red]送出失敗：{exc.detail}[/red]")
