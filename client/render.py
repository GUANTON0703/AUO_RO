from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from server.content import load_content
from server.progression.levels import base_exp_for_next, job_exp_for_next

_content = load_content()

_TIER_BY_JOB = {}
for _job in _content.jobs.values():
    _TIER_BY_JOB[_job.id] = getattr(_job, "tier", "first")


def _job_name(job_id: str) -> str:
    job = _content.jobs.get(job_id)
    return job.name if job else job_id


def _map_name(map_id: str) -> str:
    m = _content.maps.get(map_id)
    return m.name if m else map_id


def _bar(cur: int, total: int, width: int = 20) -> str:
    total = max(total, 1)
    ratio = max(0.0, min(1.0, cur / total))
    filled = int(ratio * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {cur}/{total} ({ratio * 100:.0f}%)"


def status_panel(character: dict) -> Panel:
    c = character
    job_id = c.get("job_id", "novice")
    tier = _TIER_BY_JOB.get(job_id, "first")
    base_need = base_exp_for_next(c.get("base_level", 1))
    job_need = job_exp_for_next(c.get("job_level", 1), tier)

    lines = [
        f"[bold]{c.get('name', '?')}[/bold]　{_job_name(job_id)}",
        f"Base Lv {c.get('base_level', 1)}  {_bar(c.get('base_exp', 0), base_need)}",
        f"Job  Lv {c.get('job_level', 1)}  {_bar(c.get('job_exp', 0), job_need)}",
    ]
    hp_cur = c.get("hp", c.get("hunt_hp"))
    sp_cur = c.get("sp", c.get("hunt_sp"))
    if hp_cur is not None or "max_hp" in c:
        lines.append(f"HP {_bar(hp_cur or 0, c.get('max_hp', 0))}")
    if sp_cur is not None or "max_sp" in c:
        lines.append(f"SP {_bar(sp_cur or 0, c.get('max_sp', 0))}")
    lines.append(f"Zeny {c.get('zeny', 0)}")
    loc = c.get("hunting_map_id") or c.get("location_map")
    if loc:
        lines.append(f"地點 {_map_name(loc)}")
    return Panel("\n".join(lines), title="角色狀態", expand=False)


def event_lines(events: list[dict]) -> list:
    out: list = []
    for e in events:
        kind = e.get("kind")
        if kind == "kill_batch":
            out.append(
                Text(
                    f"擊殺 {e.get('monster_name', '?')} ×{e.get('count', 0)}"
                    f"　+經驗 {e.get('base_exp', 0)}/{e.get('job_exp', 0)}"
                    f"　+Zeny {e.get('zeny', 0)}"
                )
            )
        elif kind == "rare_drop":
            out.append(
                Text(
                    f"★ 稀有掉落 {e.get('item_name', e.get('item_id', '?'))} ×{e.get('qty', 1)}",
                    style="yellow",
                )
            )
        elif kind == "potion_used":
            out.append(
                Text(
                    f"  使用 {e.get('item_name', e.get('item_id', '?'))} ×{e.get('count', 0)}"
                    f"（剩 {e.get('remaining', 0)}）",
                    style="dim",
                )
            )
        elif kind == "retreat":
            out.append(
                Text(
                    f"撤退：{e.get('reason', '')}"
                    f"（撐了 {e.get('seconds_survived', 0):.0f} 秒）",
                    style="red",
                )
            )
        else:
            out.append(Text(str(e), style="dim"))
    return out


def inventory_table(inv: dict) -> Table:
    table = Table(title="背包", expand=False)
    table.add_column("類型")
    table.add_column("名稱")
    table.add_column("數量/資訊")
    for item_id, qty in (inv.get("items") or {}).items():
        table.add_row("道具", item_id, str(qty))
    for eq in inv.get("equipment") or []:
        info = f"+{eq.get('refine', 0)}"
        if eq.get("equipped_slot"):
            info += f"　[裝備中:{eq['equipped_slot']}]"
        cards = eq.get("card_ids") or []
        if cards:
            info += f"　卡:{','.join(cards)}"
        table.add_row(
            "裝備",
            f"#{eq.get('id', '?')} {eq.get('equipment_id', '?')}",
            info,
        )
    return table


def shop_table(shop: dict) -> Table:
    table = Table(title="商店", expand=False)
    table.add_column("ID")
    table.add_column("名稱")
    table.add_column("價格")
    table.add_column("類型/部位")
    for i in shop.get("items") or []:
        table.add_row(i.get("id", "?"), i.get("name", ""), str(i.get("price", "")), i.get("kind", ""))
    for e in shop.get("equipment") or []:
        table.add_row(e.get("id", "?"), e.get("name", ""), str(e.get("price", "")), e.get("slot", ""))
    return table


def storage_table(storage: dict) -> Table:
    table = Table(title="倉庫", expand=False)
    table.add_column("類型")
    table.add_column("名稱")
    table.add_column("數量/資訊")
    for item_id, qty in (storage.get("items") or {}).items():
        table.add_row("道具", item_id, str(qty))
    for eq in storage.get("equipment") or []:
        table.add_row(
            "裝備", f"#{eq.get('id', '?')} {eq.get('equipment_id', '?')}", f"+{eq.get('refine', 0)}"
        )
    return table


def hunt_summary(status: dict) -> Panel:
    lines = [
        f"擊殺 {status.get('kills', 0)}",
        f"經驗 +{status.get('base_exp', 0)} / Job +{status.get('job_exp', 0)}",
        f"Zeny +{status.get('zeny', 0)}",
        f"有效時間 {status.get('effective_seconds', 0):.0f} 秒"
        + ("（離線效率）" if status.get("offline") else ""),
    ]
    if status.get("retreated"):
        lines.append(f"[red]已撤退：{status.get('retreat_reason', '')}[/red]")
    drops = status.get("drops") or {}
    if drops:
        lines.append("掉落 " + "、".join(f"{k}×{v}" for k, v in drops.items()))
    return Panel("\n".join(lines), title="掛機結算", expand=False)
