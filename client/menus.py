from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from client.api import ApiError
from client.render import event_lines, inventory_table, shop_table, storage_table
from server.content import load_content
from server.progression.stats import (
    STAT_KEYS, STAT_MAX, raise_cost, stat_points_available,
)

_STAT_ZH = {"str": "力量", "agi": "敏捷", "vit": "體質",
            "int": "智力", "dex": "靈巧", "luk": "幸運"}

_content = load_content()
_console = Console()


def _cid(character: dict) -> int:
    return character["id"]


def _report(console: Console, result) -> None:
    if isinstance(result, dict) and result.get("message"):
        console.print(result["message"])
    else:
        console.print("[green]完成[/green]")


def _cost_run(frm, to):
    return sum(raise_cost(v) for v in range(frm, to))


def stats_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    cur = {k: character.get(f"stat_{k}", 1) for k in STAT_KEYS}
    pending = {k: 0 for k in STAT_KEYS}
    base_level = character.get("base_level", 1)

    while True:
        spent = sum(_cost_run(cur[k], cur[k] + pending[k]) for k in STAT_KEYS)
        avail = stat_points_available(base_level, cur) - spent
        console.print(f"\n可用點數：[bold]{avail}[/bold]")
        for i, k in enumerate(STAT_KEYS, 1):
            v = cur[k] + pending[k]
            cost = raise_cost(v)
            afford = ("" if (avail >= cost and v < STAT_MAX)
                      else "  [dim](點數不足)[/dim]" if v < STAT_MAX
                      else "  [dim](已滿)[/dim]")
            console.print(f"  [cyan]{i}[/cyan]) {_STAT_ZH[k]} {v}　→ +1 需 {cost} 點{afford}")
        console.print("  [cyan]0[/cyan]) 完成")
        raw = Prompt.ask("加哪個").strip()
        if raw == "0":
            break
        if raw.isdigit() and 1 <= int(raw) <= 6:
            k = STAT_KEYS[int(raw) - 1]
            v = cur[k] + pending[k]
            if v < STAT_MAX and avail >= raise_cost(v):
                pending[k] += 1
            else:
                console.print("[red]加不了[/red]")
        else:
            console.print("[red]輸入 1-6 或 0[/red]")

    deltas = {k: n for k, n in pending.items() if n > 0}
    if not deltas:
        console.print("沒有加點。")
        return
    try:
        api.allocate_stats(character["id"], deltas)
        console.print(f"[green]已加：{deltas}[/green]")
    except Exception as exc:
        console.print(f"[red]加點失敗：{exc}[/red]")


def skills_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    job_id = character.get("job_id", "novice")
    skills = [s for s in _content.skills.values() if s.job_id == job_id]
    if not skills:
        console.print("此職業沒有可學技能。")
        return
    for s in skills:
        console.print(f"  {s.id}　{s.name}（{s.kind}，max {s.max_level}）")
    skill_id = Prompt.ask("學哪個技能（skill_id）")
    level = IntPrompt.ask("學到幾級", default=1)
    try:
        api.learn_skill(_cid(character), skill_id, level)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    console.print("[green]已學習[/green]")


def equip_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    inv = api.inventory(_cid(character))
    console.print(inventory_table(inv))
    equipment = inv.get("equipment") or []
    if not equipment:
        console.print("背包沒有裝備。")
        return
    inst = IntPrompt.ask("穿哪件（裝備 #編號，0 取消）", default=0)
    if inst:
        try:
            api.equip(_cid(character), inst)
            console.print("[green]已裝備[/green]")
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")
    if Confirm.ask("要卸下某個部位嗎", default=False):
        slot = Prompt.ask("部位（weapon/armor/...）")
        try:
            api.unequip(_cid(character), slot)
            console.print("[green]已卸下[/green]")
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")


def refine_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    inv = api.inventory(_cid(character))
    refinable = [
        e for e in (inv.get("equipment") or [])
        if getattr(_content.equipment.get(e.get("equipment_id")), "refinable", False)
    ]
    if not refinable:
        console.print("沒有可精煉的裝備。")
        return
    for e in refinable:
        eq = _content.equipment.get(e["equipment_id"])
        console.print(f"  #{e['id']} {eq.name} +{e.get('refine', 0)}")
    inst = IntPrompt.ask("精煉哪件（#編號，0 取消）", default=0)
    if not inst:
        return
    if not Confirm.ask("確認精煉（可能失敗降級）", default=True):
        return
    try:
        result = api.refine(_cid(character), inst)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    _report(console, result)


def socket_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    inv = api.inventory(_cid(character))
    cards = {
        iid: qty for iid, qty in (inv.get("items") or {}).items()
        if iid in _content.cards
    }
    slotted = []
    for e in inv.get("equipment") or []:
        eq = _content.equipment.get(e.get("equipment_id"))
        if eq and len(e.get("card_ids") or []) < getattr(eq, "card_slots", 0):
            slotted.append((e, eq))
    if not slotted or not cards:
        console.print("沒有可鑲嵌的裝備或卡片。")
        return
    for e, eq in slotted:
        console.print(f"  #{e['id']} {eq.name}（空孔 {eq.card_slots - len(e.get('card_ids') or [])}）")
    console.print("卡片：" + "　".join(f"{k}×{v}" for k, v in cards.items()))
    inst = IntPrompt.ask("鑲到哪件（#編號）")
    card_id = Prompt.ask("哪張卡（card_id）")
    try:
        api.socket(_cid(character), inst, card_id)
        console.print("[green]已鑲嵌[/green]")
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")


def shop_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    shop = api.shop()
    console.print(shop_table(shop))
    action = Prompt.ask("動作", choices=["buy", "sell", "cancel"], default="cancel")
    if action == "cancel":
        return
    item_id = Prompt.ask("道具 id")
    qty = IntPrompt.ask("數量", default=1)
    try:
        if action == "buy":
            result = api.buy(item_id, qty)
        else:
            result = api.sell(item_id=item_id, qty=qty)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    console.print(f"[green]{result}[/green]")


def storage_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    console.print(storage_table(api.storage()))
    console.print(inventory_table(api.inventory(_cid(character))))
    action = Prompt.ask("動作", choices=["deposit", "withdraw", "cancel"], default="cancel")
    if action == "cancel":
        return
    item_id = Prompt.ask("道具 id")
    qty = IntPrompt.ask("數量", default=1)
    try:
        if action == "deposit":
            api.deposit(item_id=item_id, qty=qty)
        else:
            api.withdraw(item_id=item_id, qty=qty)
        console.print("[green]完成[/green]")
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")


def jobchange_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    job_id = character.get("job_id", "novice")
    job_level = character.get("job_level", 1)
    targets = [j for j in _content.jobs.values() if getattr(j, "parent_id", None) == job_id]
    if not targets:
        console.print("目前職業沒有可轉的下一職。")
        return
    for j in targets:
        need = getattr(j, "change_job_level", 1)
        mark = "可轉" if job_level >= need else f"需 Job Lv {need}"
        console.print(f"  {j.id}　{j.name}（{mark}）")
    target = Prompt.ask("轉哪個（job_id，cancel 取消）", default="cancel")
    if target == "cancel":
        return
    try:
        api.jobchange(_cid(character), target)
        console.print("[green]轉職成功[/green]")
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")


def _fmt_remain(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m = rem // 60
    if h:
        return f"剩 {h}h {m}m"
    return f"剩 {m}m"


_RANK_KEYS = ["base_level", "job_level", "zeny", "cards", "refine"]


def rank_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    by = Prompt.ask("排序依據", choices=_RANK_KEYS, default="base_level")
    try:
        rows = api.leaderboard(by)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    table = Table(title=f"排行榜 · {by}")
    table.add_column("#", justify="right")
    table.add_column("角色")
    table.add_column("帳號")
    table.add_column(by, justify="right")
    for i, r in enumerate(rows or [], 1):
        table.add_row(str(i), str(r.get("character_name", "")),
                      str(r.get("account", "")), str(r.get("value", "")))
    console.print(table)


def _fmt_trade_items(items) -> str:
    parts = []
    for it in items:
        if it.get("item_id"):
            parts.append(f"{it['item_id']}×{it['qty']}")
        else:
            parts.append(f"裝備#{it.get('equipment_id')}")
    return "、".join(parts) or "（空）"


def _print_trade(console: Console, tbl: dict) -> None:
    console.print(f"[bold]交易 #{tbl['id']}[/bold]　狀態：{tbl['status']}")
    items = tbl.get("items") or []
    fm = [it for it in items if it["side"] == "from"]
    to = [it for it in items if it["side"] == "to"]
    console.print(f"  發起方 {'[green]✔[/green]' if tbl['from_confirmed'] else '·'}：{_fmt_trade_items(fm)}")
    console.print(f"  受邀方 {'[green]✔[/green]' if tbl['to_confirmed'] else '·'}：{_fmt_trade_items(to)}")


def _trade_screen(api, tid: int, console: Console) -> None:
    while True:
        try:
            tbl = api.trade_get(tid)
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")
            return
        _print_trade(console, tbl)
        if tbl["status"] != "open":
            console.print(f"[yellow]交易已結束：{tbl['status']}[/yellow]")
            return
        act = Prompt.ask("動作", choices=["put", "confirm", "cancel", "refresh", "back"],
                         default="refresh")
        if act == "back":
            return
        try:
            if act == "put":
                item_id = Prompt.ask("道具 id（留空改放裝備）", default="")
                if item_id:
                    qty = IntPrompt.ask("數量", default=1)
                    api.trade_put(tid, item_id=item_id, qty=qty)
                else:
                    eid = IntPrompt.ask("裝備實例 id")
                    api.trade_put(tid, equipment_instance_id=eid)
            elif act == "confirm":
                res = api.trade_confirm(tid) or {}
                if res.get("status") == "done":
                    console.print("[green]交易完成！[/green]")
                    return
                console.print("[dim]已確認，等待對方。[/dim]")
            elif act == "cancel":
                api.trade_cancel(tid)
                console.print("[yellow]已取消交易。[/yellow]")
                return
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")


def trade_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    try:
        pend = api.trade_pending() or []
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    if pend:
        console.print("別人開給你的交易：")
        for t in pend:
            console.print(f"  #{t['id']}　來自帳號 {t.get('from_account')}")
    choice = Prompt.ask("輸入交易 #id 進入、new 開新交易、cancel 離開", default="cancel")
    if choice == "cancel":
        return
    if choice == "new":
        who = Prompt.ask("對方帳號名")
        try:
            tid = api.trade_offer(who)["trade_id"]
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")
            return
    else:
        try:
            tid = int(choice)
        except ValueError:
            console.print("[red]無效輸入。[/red]")
            return
    _trade_screen(api, tid, console)


def guild_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    try:
        mine = api.guild_mine()
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    if mine:
        console.print(f"[bold]公會：{mine['name']}[/bold]")
        for m in mine.get("members") or []:
            console.print(f"  {m['character_name']}（{m['role']}）")
        if Prompt.ask("動作", choices=["leave", "back"], default="back") == "leave":
            try:
                api.guild_leave()
                console.print("[green]已退會。[/green]")
            except ApiError as exc:
                console.print(f"[red]{exc.detail}[/red]")
        return
    try:
        guilds = api.guild_list() or []
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    if guilds:
        console.print("現有公會：")
        for g in guilds:
            console.print(f"  #{g['id']}　{g['name']}（{g.get('member_count', 0)} 人）")
    else:
        console.print("目前還沒有公會。")
    choice = Prompt.ask("輸入 join <id> 或 create <名稱>，cancel 離開", default="cancel")
    if choice == "cancel":
        return
    try:
        if choice.startswith("join "):
            api.guild_join(int(choice.split(None, 1)[1]))
            console.print("[green]已加入公會。[/green]")
        elif choice.startswith("create "):
            api.guild_create(choice.split(None, 1)[1])
            console.print("[green]已建立公會。[/green]")
        else:
            console.print("[red]無效輸入。[/red]")
    except (ApiError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")


def mvp_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    try:
        mvps = api.list_mvp()
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return

    ready = []
    for m in mvps:
        if m["available"]:
            mark = "[green]可挑戰[/green]"
            ready.append(m["id"])
        else:
            mark = f"[dim]{_fmt_remain(m['seconds_remaining'])}[/dim]"
        console.print(
            f"  {m['id']}　{m['name']}　Lv {m['level']}　{m['home_map_name']}　{mark}"
        )
    if not ready:
        console.print("目前沒有可挑戰的 MVP。")
        return

    target = Prompt.ask("挑戰哪隻（mvp_id，cancel 取消）", default="cancel")
    if target == "cancel" or target not in ready:
        if target != "cancel":
            console.print("[yellow]該 MVP 無法挑戰。[/yellow]")
        return

    flee = IntPrompt.ask("auto-flee 血線 %（0 = 硬拚）", default=15)
    if not Confirm.ask(f"確認挑戰 {target}？", default=True):
        return

    try:
        result = api.challenge_mvp(target, flee_hp_frac=flee / 100 if flee > 0 else 0.0)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return

    for line in event_lines(result.get("events", [])):
        console.print(line)

    outcome = result.get("outcome")
    if outcome == "win":
        drops = result.get("drops") or {}
        drop_txt = "、".join(f"{k}×{v}" for k, v in drops.items()) or "無"
        console.print(
            f"[green]擊殺成功！經驗 +{result.get('base_exp', 0)}/"
            f"{result.get('job_exp', 0)}　Zeny +{result.get('zeny', 0)}　掉落 {drop_txt}[/green]"
        )
    elif outcome == "loss":
        console.print(f"[red]戰敗，損失經驗 {result.get('exp_penalty', 0)}。[/red]")
    else:
        console.print("[yellow]已撤退，未損失經驗（進入短冷卻）。[/yellow]")
