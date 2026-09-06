import threading
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from client.api import ApiClient, ApiError
from client.render import event_lines, hunt_status_panel, hunt_summary, retreat_advice

# 單一批次事件超過這個行數就不逐行播，直接倒完（離線追趕、長時間空窗）
_BIG_BATCH_LINES = 20
_HISTORY_CAP = 200


def _frame(character_panel, status: dict, events: list, elapsed: float | None):
    hunt_panel = hunt_status_panel(status, elapsed)
    if character_panel:
        top = Table.grid(expand=True)
        top.add_column(ratio=1)
        top.add_column(ratio=1)
        top.add_row(character_panel, hunt_panel)
    else:
        top = hunt_panel
    recent = events[-10:] or ["搜尋目標中…"]
    return Group(
        top,
        Panel(Group(*recent), title="即時戰鬥紀錄", height=14, expand=True),
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

    history: list = []
    pending: list = []
    last_batch_id = None
    last_pop = time.monotonic()
    # 掛機時間本地補間：記住伺服器回的秒數與收到的時刻，畫面上自己往前跑
    server_secs = 0.0
    server_secs_at = time.monotonic()
    last_status: dict = {}
    error = None
    no_hunt_message = None
    # 全螢幕緩衝區：畫面不會被過高的內容擠爆、離開時自動還原。
    # 非終端機（測試錄製 console）時關掉，否則輸出抓不到。
    use_screen = bool(getattr(console, "is_terminal", False))
    with Live(console=console, refresh_per_second=4, screen=use_screen) as live:
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

            batch_id = status.get("batch_id")
            if batch_id is not None and batch_id != last_batch_id:
                last_batch_id = batch_id
                server_secs = float(status.get("effective_seconds", 0) or 0)
                server_secs_at = time.monotonic()
                lines = event_lines(status.get("events", []))
                if status.get("offline") or len(lines) > _BIG_BATCH_LINES:
                    if status.get("offline"):
                        history.append(Text(
                            f"— 離線結算：擊殺 {status.get('kills', 0)}，"
                            f"經驗 +{status.get('base_exp', 0)}/{status.get('job_exp', 0)}，"
                            f"Zeny +{status.get('zeny', 0)} —", style="dim"))
                    history.extend(lines)
                    pending.clear()
                else:
                    pending.extend(lines)

            if pending and time.monotonic() - last_pop >= 1.0:
                history.append(pending.pop(0))
                last_pop = time.monotonic()
            if len(history) > _HISTORY_CAP:
                del history[:-_HISTORY_CAP]

            elapsed = server_secs + (time.monotonic() - server_secs_at)
            live.update(_frame(character_panel, status, history, elapsed), refresh=True)
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
