import threading

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from client.api import ApiClient, ApiError
from client.render import event_lines, hunt_status_panel, hunt_summary, retreat_advice


def _frame(character_panel, status: dict, events: list):
    hunt_panel = hunt_status_panel(status)
    if character_panel:
        top = Table.grid(expand=True)
        top.add_column(ratio=1)
        top.add_column(ratio=1)
        top.add_row(character_panel, hunt_panel)
    else:
        top = hunt_panel
    recent = events[-24:] or ["等待伺服器回傳戰鬥事件…"]
    return Group(
        top,
        Panel(Group(*recent), title="即時戰鬥紀錄", height=14),
        "[dim]按 Enter 停止觀看（掛機仍在伺服器繼續）。[/dim]",
    )


def watch_hunt(api: ApiClient, console: Console, poll_seconds: float = 1.0,
               render_status=None) -> None:
    stop = threading.Event()

    def _wait_enter() -> None:
        try:
            input()
        except (EOFError, RuntimeError):
            pass
        stop.set()

    threading.Thread(target=_wait_enter, daemon=True).start()

    history = []
    last_status = {}
    error = None
    no_hunt_message = None
    with Live(console=console, refresh_per_second=4, transient=False) as live:
        while True:
            try:
                status = api.hunt_status()
            except ApiError as exc:
                if exc.status == 409:
                    no_hunt_message = "目前沒有正在掛機，請先按 h 開始掛機。"
                else:
                    error = exc
                break
            except Exception as exc:
                error = exc
                break
            last_status = status
            character_panel = render_status(status) if render_status else None
            history.extend(event_lines(status.get("events", [])))
            live.update(_frame(character_panel, status, history), refresh=True)
            if status.get("retreated") or stop.wait(poll_seconds):
                break
    if no_hunt_message is not None:
        console.print(f"[yellow]{no_hunt_message}[/yellow]")
    elif error is not None:
        console.print(f"[red]結算失敗：{error}[/red]")
    elif last_status.get("retreated"):
        console.print(hunt_summary(last_status))
        console.print(
            f"[yellow]建議：{retreat_advice(last_status.get('retreat_reason', ''))}[/yellow]"
        )
        console.print("[yellow]已撤退，掛機結束。[/yellow]")
    console.print("[dim]停止觀看。[/dim]")
