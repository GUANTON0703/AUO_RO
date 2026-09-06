import threading

from rich.console import Console

from client.api import ApiClient, ApiError


def chat_mode(
    api: ApiClient,
    console: Console | None = None,
    has_guild: bool = False,
    poll_seconds: float = 3.0,
) -> None:
    console = console or Console()

    channels = ["world"]
    if has_guild:
        try:
            mine = api.guild_mine()
        except ApiError:
            mine = None
        if mine:
            channels.append(f"guild:{mine['id']}")

    console.print("[dim]聊天模式：輸入文字送到世界頻道，空行離開。[/dim]")
    stop = threading.Event()

    def _reader() -> None:
        while not stop.is_set():
            try:
                line = input()
            except (EOFError, RuntimeError):
                stop.set()
                return
            if not line.strip():
                stop.set()
                return
            try:
                api.chat_post("world", line.strip())
            except ApiError as exc:
                console.print(f"[red]送出失敗：{exc.detail}[/red]")

    threading.Thread(target=_reader, daemon=True).start()

    last = {ch: 0 for ch in channels}
    for ch in channels:
        try:
            msgs = api.chat_since(ch, 0) or []
        except ApiError:
            continue
        if msgs:
            last[ch] = msgs[-1]["id"]

    while not stop.wait(poll_seconds):
        for ch in channels:
            try:
                msgs = api.chat_since(ch, last[ch]) or []
            except ApiError:
                continue
            for m in msgs:
                last[ch] = m["id"]
                tag = "" if ch == "world" else "[magenta][公會][/magenta] "
                console.print(f"{tag}[cyan]{m['character_name']}[/cyan]：{m['text']}")

    console.print("[dim]離開聊天。[/dim]")
