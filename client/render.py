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


def _item_name(item_id: str) -> str:
    for collection in (_content.items, _content.equipment, _content.cards):
        item = collection.get(item_id)
        if item:
            return f"{item.name}（{item_id}）"
    return item_id


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


def newbie_hint_panel() -> Panel:
    return Panel(
        "你的角色還很弱，建議依序：\n"
        "  1. [cyan]stats[/cyan] 加點——先把 力量 和 體質 拉到 10 以上\n"
        "  2. [cyan]skills[/cyan] 學技能——先點主力輸出技（劍士→爆裂波動）\n"
        "  3. [cyan]shop[/cyan] 商店——買紅色藥水補血\n"
        "  4. [cyan]h[/cyan] 掛機——去「東門村郊」打最弱的怪",
        title="新手指引", border_style="yellow",
    )


def hunt_status_panel(status: dict) -> Panel:
    state = "撤退" if status.get("retreated") else "進行中"
    monster = status.get("monster_name") or status.get("monster_id", "未知")
    lines = [
        f"狀態：{state}",
        f"目標：{monster}",
        f"擊殺：{status.get('kills', 0)}",
        f"Base EXP：+{status.get('base_exp', 0)}",
        f"Job EXP：+{status.get('job_exp', 0)}",
        f"Zeny：+{status.get('zeny', 0)}",
        f"掛機時間：{status.get('effective_seconds', 0):.0f} 秒",
    ]
    return Panel("\n".join(lines), title="掛機狀態", expand=False)


_ADVICE = {
    "戰鬥中被擊倒": "這裡的怪太強。先 stats 加點提升力量/體質，或換更低等的地圖，或 shop 買裝備。",
    "打不過這裡的怪": "完全打不動。回東門村郊打最弱的怪，或先加點、買武器。",
    "沒有補品，血量見底": "帶紅色藥水再來（shop 買），或打更弱的怪讓自然回血跟得上。",
    "補品用盡，血量見底": "補品不夠。多買幾瓶紅色藥水，或換更好打的怪。",
    "補品用盡": "補品不夠。多買幾瓶紅色藥水。",
}


def retreat_advice(reason: str) -> str:
    return _ADVICE.get(reason, "換個地方打打看，或先提升角色數值。")


_COMBAT_KINDS = {"attack", "skill", "fled"}


def event_lines(events: list[dict], max_combat_lines: int = 20) -> list:
    out: list = []
    combat_idx: list[int] = []
    for e in events:
        kind = e.get("kind")
        if kind == "attack":
            actor = e.get("actor", "?")
            target = e.get("target", "?")
            if not e.get("hit", True):
                out.append(Text(f"  {actor} 攻擊 {target} → MISS", style="dim"))
            else:
                tag = "　暴擊!" if e.get("crit") else ""
                out.append(Text(
                    f"  {actor} 攻擊 {target} → {e.get('damage', 0)} 傷害{tag}", style="dim"
                ))
            combat_idx.append(len(out) - 1)
            continue
        if kind == "skill":
            out.append(Text(
                f"  {e.get('actor', '?')} 施放【{e.get('skill_name', e.get('skill_id', '?'))}】"
                f" → {e.get('damage', 0)}", style="dim"
            ))
            combat_idx.append(len(out) - 1)
            continue
        if kind == "fled":
            out.append(Text(
                f"撤退，剩 {e.get('hp', 0)} HP", style="yellow"
            ))
            combat_idx.append(len(out) - 1)
            continue
        if kind == "challenge_result":
            oc = e.get("outcome")
            label = {"win": "勝利", "loss": "落敗", "fled": "已撤退"}.get(oc, oc)
            parts = [f"挑戰結果：{label}（{e.get('rounds', 0)} 回合）"]
            if e.get("base_exp") or e.get("job_exp"):
                parts.append(f"經驗 +{e.get('base_exp', 0)}/{e.get('job_exp', 0)}")
            if e.get("zeny"):
                parts.append(f"Zeny +{e.get('zeny', 0)}")
            if e.get("exp_penalty"):
                parts.append(f"經驗 -{e.get('exp_penalty', 0)}")
            drops = e.get("drops") or {}
            if drops:
                parts.append("掉落 " + "、".join(f"{k}×{v}" for k, v in drops.items()))
            out.append(Text("　".join(parts),
                            style="green" if oc == "win" else "yellow"))
            continue
        _legacy_event_line(out, e, kind)

    if len(combat_idx) > max_combat_lines:
        keep_head = {combat_idx[i] for i in range(10)}
        keep_tail = {combat_idx[i] for i in range(len(combat_idx) - 10, len(combat_idx))}
        omitted = len(combat_idx) - 20
        new_out: list = []
        inserted = False
        for i, line in enumerate(out):
            if i in combat_idx and i not in keep_head and i not in keep_tail:
                if not inserted:
                    new_out.append(Text(f"  …省略 {omitted} 條…", style="dim"))
                    inserted = True
                continue
            new_out.append(line)
        return new_out
    return out


def _legacy_event_line(out: list, e: dict, kind: str) -> None:
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
                f"★ 稀有掉落 {_item_name(e.get('item_id', '?'))} ×{e.get('qty', 1)}",
                style="yellow",
            )
        )
    elif kind == "potion_used":
        out.append(
            Text(
                f"  使用 {_item_name(e.get('item_id', '?'))} ×{e.get('count', 0)}"
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
    elif kind == "kill":
        out.append(Text(f"{e.get('actor', '?')} 擊倒了 {e.get('target', '?')}", style="bold"))
    elif kind in ("status_applied", "status_expired"):
        pass  # 狀態變化不逐條顯示
    else:
        out.append(Text(str(e), style="dim"))


def inventory_table(inv: dict) -> Table:
    table = Table(title="背包", expand=False)
    table.add_column("類型")
    table.add_column("名稱")
    table.add_column("數量/資訊")
    for item_id, qty in (inv.get("items") or {}).items():
        table.add_row("道具", _item_name(item_id), str(qty))
    for eq in inv.get("equipment") or []:
        info = f"+{eq.get('refine', 0)}"
        if eq.get("equipped_slot"):
            info += f"　[裝備中:{eq['equipped_slot']}]"
        cards = eq.get("card_ids") or []
        if cards:
            info += f"　卡:{','.join(cards)}"
        table.add_row(
            "裝備",
            f"#{eq.get('id', '?')} {_item_name(eq.get('equipment_id', '?'))}",
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
        table.add_row(i.get("id", "?"), _item_name(i.get("id", "?")), str(i.get("price", "")), i.get("kind", ""))
    for e in shop.get("equipment") or []:
        table.add_row(e.get("id", "?"), _item_name(e.get("id", "?")), str(e.get("price", "")), e.get("slot", ""))
    return table


def storage_table(storage: dict) -> Table:
    table = Table(title="倉庫", expand=False)
    table.add_column("類型")
    table.add_column("名稱")
    table.add_column("數量/資訊")
    for item_id, qty in (storage.get("items") or {}).items():
        table.add_row("道具", _item_name(item_id), str(qty))
    for eq in storage.get("equipment") or []:
        table.add_row(
            "裝備", f"#{eq.get('id', '?')} {_item_name(eq.get('equipment_id', '?'))}", f"+{eq.get('refine', 0)}"
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
        lines.append("掉落 " + "、".join(f"{_item_name(k)}×{v}" for k, v in drops.items()))
    return Panel("\n".join(lines), title="掛機結算", expand=False)
