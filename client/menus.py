from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from client.api import ApiError
from client.render import event_lines, inventory_table, shop_table, storage_table
from server.content import load_content
from server.progression.stats import STAT_KEYS, stat_points_available

_content = load_content()
_console = Console()


def _cid(character: dict) -> int:
    return character["id"]


def _report(console: Console, result) -> None:
    if isinstance(result, dict) and result.get("message"):
        console.print(result["message"])
    else:
        console.print("[green]完成[/green]")


def stats_menu(api, character: dict, console: Console | None = None) -> None:
    console = console or _console
    stats = {k: character.get(f"stat_{k}", 1) for k in STAT_KEYS}
    avail = stat_points_available(character.get("base_level", 1), stats)
    console.print("目前屬性：" + "　".join(f"{k.upper()} {v}" for k, v in stats.items()))
    console.print(f"可用屬性點：約 {avail}")
    which = Prompt.ask("加哪個屬性", choices=list(STAT_KEYS))
    amount = IntPrompt.ask("加幾點", default=1)
    if amount <= 0:
        return
    try:
        result = api.allocate_stats(_cid(character), {which: amount})
    except ApiError as exc:
        console.print(f"[red]{exc.detail}[/red]")
        return
    _report(console, result)


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
