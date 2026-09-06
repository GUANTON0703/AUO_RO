from rich.console import Console
from rich.prompt import Prompt as RichPrompt
from rich.table import Table


class Prompt:
    """Local input adapter so menu prompts cannot monkeypatch the chooser."""

    ask = staticmethod(RichPrompt.ask)


def choose(console: Console, title: str, rows: list, *, allow_back: bool = True):
    """rows: [(label, value)]。印編號選單，回選中的 value；allow_back 時 0 回 None。"""
    if not rows:
        console.print("[dim](沒有可選項目)[/dim]")
        return None
    console.print(f"[bold]{title}[/bold]")
    for i, (label, _) in enumerate(rows, 1):
        console.print(f"  [cyan]{i}[/cyan]) {label}")
    if allow_back:
        console.print("  [cyan]0[/cyan]) 返回")
    while True:
        raw = Prompt.ask("選擇").strip()
        if raw == "0" and allow_back:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1][1]
        console.print("[red]請輸入清單上的編號[/red]")


def choose_many(console: Console, title: str, rows: list, *, allow_back: bool = True):
    """rows: [(label, value)]。印編號選單，讀逗號或空白分隔的多個編號，回選中的 value list。
    留空 = 回傳 []（代表自動）。allow_back 目前僅用於提示一致性。"""
    if not rows:
        console.print("[dim](沒有可選項目)[/dim]")
        return []
    console.print(f"[bold]{title}[/bold]")
    for i, (label, _) in enumerate(rows, 1):
        console.print(f"  [cyan]{i}[/cyan]) {label}")
    while True:
        raw = Prompt.ask("選擇（可多選，逗號或空白分隔；留空 = 自動）").strip()
        if not raw:
            return []
        parts = raw.replace(",", " ").split()
        if all(p.isdigit() and 1 <= int(p) <= len(rows) for p in parts):
            seen = []
            for p in parts:
                v = rows[int(p) - 1][1]
                if v not in seen:
                    seen.append(v)
            return seen
        console.print("[red]請輸入清單上的編號（可多個，例如 1,3），留空 = 自動[/red]")


def choose_table(title: str, rows: list) -> Table:
    table = Table(title=title, expand=False)
    table.add_column("#", justify="right")
    table.add_column("選項")
    for i, (label, _value) in enumerate(rows, 1):
        table.add_row(str(i), str(label))
    return table
