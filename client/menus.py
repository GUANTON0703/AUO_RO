from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from client.api import ApiError
from client.render import event_lines, inventory_table, shop_table, storage_table
from client.ui import choose
from server.content import load_content
from server.loot.refine import (
    refine_ore_for, refine_zeny_cost, success_rate,
)
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


def _eq_name(equipment_id: str) -> str:
    eq = _content.equipment.get(equipment_id)
    return eq.name if eq else equipment_id


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
    learned = character.get("learned_skills") or {}
    points = character.get("skill_points", 0)
    rows = []
    for s in _content.skills.values():
        if s.job_id != job_id:
            continue
        have = learned.get(s.id, 0)
        if have >= s.max_level:
            continue
        rows.append((f"{s.name}  Lv{have}/{s.max_level}  +1 需 1 點", s.id))
    if not rows:
        console.print("沒有可學的本職技能。")
        return
    skill_id = choose(console, f"學哪個技能（剩 {points} 技能點）", rows)
    if skill_id is None:
        return
    target = learned.get(skill_id, 0) + 1
    try:
        api.learn_skill(_cid(character), skill_id, target)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    console.print("[green]已學習[/green]")


def equip_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    inv = api.inventory(_cid(character))
    console.print(inventory_table(inv))
    equipment = inv.get("equipment") or []

    bag = [e for e in equipment if not e.get("equipped_slot")]
    rows = [(f"#{e['id']} {_eq_name(e.get('equipment_id'))} +{e.get('refine', 0)}", e["id"])
            for e in bag]
    inst = choose(console, "穿哪件裝備", rows)
    if inst is not None:
        try:
            api.equip(_cid(character), inst)
            console.print("[green]已裝備[/green]")
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")

    worn = [e for e in equipment if e.get("equipped_slot")]
    rows = [(f"{e['equipped_slot']}：{_eq_name(e.get('equipment_id'))}", e["equipped_slot"])
            for e in worn]
    slot = choose(console, "卸下哪個部位", rows)
    if slot is not None:
        try:
            api.unequip(_cid(character), slot)
            console.print("[green]已卸下[/green]")
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")


def refine_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    inv = api.inventory(_cid(character))
    rows = []
    for e in inv.get("equipment") or []:
        eq = _content.equipment.get(e.get("equipment_id"))
        if not getattr(eq, "refinable", False):
            continue
        cur = e.get("refine", 0)
        ore = refine_ore_for(eq.slot)
        zeny = refine_zeny_cost(cur)
        pct = success_rate(cur) * 100
        rows.append(
            (f"#{e['id']} {eq.name} +{cur}  需 {ore}×1 + {zeny}z  成功率 {pct:.0f}%", e["id"])
        )
    inst = choose(console, "精煉哪件裝備", rows)
    if inst is None:
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
    cards = [
        (f"{iid}×{qty}", iid) for iid, qty in (inv.get("items") or {}).items()
        if iid in _content.cards
    ]
    slotted = []
    for e in inv.get("equipment") or []:
        eq = _content.equipment.get(e.get("equipment_id"))
        if eq and len(e.get("card_ids") or []) < getattr(eq, "card_slots", 0):
            free = eq.card_slots - len(e.get("card_ids") or [])
            slotted.append((f"#{e['id']} {eq.name}（空孔 {free}）", e["id"]))
    if not slotted or not cards:
        console.print("沒有可鑲嵌的裝備或卡片。")
        return
    inst = choose(console, "鑲到哪件裝備", slotted)
    if inst is None:
        return
    card_id = choose(console, "鑲哪張卡", cards)
    if card_id is None:
        return
    try:
        api.socket(_cid(character), inst, card_id)
        console.print("[green]已鑲嵌[/green]")
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")


def shop_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    shop = api.shop()
    console.print(shop_table(shop))
    action = choose(console, "商店", [("買", "buy"), ("賣", "sell")])
    if action is None:
        return
    if action == "buy":
        rows = [(f"{i.get('name', i['id'])}  {i.get('price', '?')}z", i["id"])
                for i in (shop.get("items") or [])]
        rows += [(f"{e.get('name', e['id'])}  {e.get('price', '?')}z", e["id"])
                 for e in (shop.get("equipment") or [])]
        item_id = choose(console, "買什麼", rows)
        if item_id is None:
            return
        qty = IntPrompt.ask("數量", default=1)
        try:
            result = api.buy(item_id, qty)
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")
            return
        console.print(f"[green]{result}[/green]")
        return

    inv = api.inventory(_cid(character))
    rows = [(f"{iid}×{qty}", ("item", iid))
            for iid, qty in (inv.get("items") or {}).items()]
    rows += [(f"#{e['id']} {_eq_name(e.get('equipment_id'))} +{e.get('refine', 0)}",
              ("equip", e["id"]))
             for e in (inv.get("equipment") or []) if not e.get("equipped_slot")]
    picked = choose(console, "賣什麼", rows)
    if picked is None:
        return
    kind, ref = picked
    try:
        if kind == "item":
            qty = IntPrompt.ask("數量", default=1)
            result = api.sell(item_id=ref, qty=qty)
        else:
            result = api.sell(equipment_instance_id=ref)
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    console.print(f"[green]{result}[/green]")


def storage_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    storage = api.storage()
    inv = api.inventory(_cid(character))
    console.print(storage_table(storage))
    console.print(inventory_table(inv))
    action = choose(console, "倉庫", [("存入", "deposit"), ("取出", "withdraw")])
    if action is None:
        return
    src = inv if action == "deposit" else storage
    rows = [(f"{iid}×{qty}", iid) for iid, qty in (src.get("items") or {}).items()]
    item_id = choose(console, "哪個物品", rows)
    if item_id is None:
        return
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
    rows = []
    for j in _content.jobs.values():
        if getattr(j, "parent_id", None) != job_id:
            continue
        need = getattr(j, "change_job_level", 1)
        if job_level >= need:
            rows.append((j.name, j.id))
        else:
            console.print(f"  [dim]{j.name}（需 Job Lv {need}）[/dim]")
    target = choose(console, "轉哪個職業", rows)
    if target is None:
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
        act = choose(console, "動作", [
            ("放入物品/裝備", "put"), ("確認交易", "confirm"),
            ("取消交易", "cancel"), ("重新整理", "refresh"),
        ])
        if act is None or act == "back":
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
    rows = [("開新交易", ("new", None))]
    for t in pend:
        rows.append((f"#{t['id']}　來自帳號 {t.get('from_account')}", ("open", t["id"])))
    picked = choose(console, "交易", rows)
    if picked is None:
        return
    kind, tid = picked
    if kind == "new":
        who = Prompt.ask("對方帳號名")
        try:
            tid = api.trade_offer(who)["trade_id"]
        except ApiError as exc:
            console.print(f"[red]{exc.detail}[/red]")
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
        if choose(console, "動作", [("退出公會", "leave")]) == "leave":
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
    rows = [("建立新公會", ("create", None))]
    for g in guilds:
        rows.append((f"{g['name']}（{g.get('member_count', 0)} 人）", ("join", g["id"])))
    picked = choose(console, "公會", rows)
    if picked is None:
        return
    kind, gid = picked
    try:
        if kind == "create":
            name = Prompt.ask("公會名稱")
            api.guild_create(name)
            console.print("[green]已建立公會。[/green]")
        else:
            api.guild_join(gid)
            console.print("[green]已加入公會。[/green]")
    except (ApiError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")


_FLEE_CHOICES = [
    ("[建議] 血剩 15% 就撤", 0.15),
    ("血剩 30% 就撤", 0.30),
    ("硬拚到底", 0.0),
]


def mvp_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    try:
        mvps = api.list_mvp()
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return

    rows = []
    for m in mvps:
        if m["available"]:
            rows.append(
                (f"{m['name']}　Lv {m['level']}　{m['home_map_name']}", m["id"])
            )
        else:
            console.print(
                f"  [dim]{m['name']}　Lv {m['level']}　"
                f"{_fmt_remain(m['seconds_remaining'])}[/dim]"
            )
    if not rows:
        console.print("目前沒有可挑戰的 MVP。")
        return

    target = choose(console, "挑戰哪隻 MVP", rows)
    if target is None:
        return

    flee = choose(console, "auto-flee 血線", _FLEE_CHOICES)
    if flee is None:
        return
    if not Confirm.ask(f"確認挑戰 {target}？", default=True):
        return

    try:
        result = api.challenge_mvp(target, flee_hp_frac=flee)
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
