import threading

from rich.console import Console

from client.api import ApiClient
from client.render import event_lines, hunt_summary, retreat_advice


def watch_hunt(api: ApiClient, console: Console, poll_seconds: float = 5.0) -> None:
    console.print("[dim]掛機中。按 Enter 停止觀看（掛機在伺服器繼續）。[/dim]")
    stop = threading.Event()

    def _wait_enter() -> None:
        try:
            input()
        except (EOFError, RuntimeError):
            pass
        stop.set()

    threading.Thread(target=_wait_enter, daemon=True).start()

    while True:
        try:
            status = api.hunt_status()
        except Exception as exc:
            console.print(f"[red]結算失敗：{exc}[/red]")
            break
        for line in event_lines(status.get("events", [])):
            console.print(line)
        if status.get("retreated"):
            console.print(hunt_summary(status))
            console.print(
                f"[yellow]建議：{retreat_advice(status.get('retreat_reason', ''))}[/yellow]"
            )
            console.print("[yellow]已撤退，掛機結束。[/yellow]")
            break
        if stop.wait(poll_seconds):
            break
    console.print("[dim]停止觀看。[/dim]")
