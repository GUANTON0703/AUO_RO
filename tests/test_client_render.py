from rich.console import Console

from client.render import (
    event_lines,
    hunt_summary,
    inventory_table,
    newbie_hint_panel,
    retreat_advice,
    shop_table,
    status_panel,
)


def _render(renderable) -> str:
    con = Console(width=80, record=True)
    con.print(renderable)
    return con.export_text()


def test_status_panel_shows_key_fields():
    ch = {
        "name": "英雄", "job_id": "swordman", "base_level": 25, "job_level": 15,
        "base_exp": 1200, "job_exp": 300, "zeny": 5000,
        "hp": 900, "max_hp": 1000, "sp": 40, "max_sp": 60,
        "location_map": "prontera_south_field",
    }
    out = _render(status_panel(ch))
    assert "英雄" in out and "25" in out and "5000" in out


def test_event_lines_formats_kill_batch_and_rare():
    events = [
        {"kind": "kill_batch", "monster_name": "波利", "count": 42, "base_exp": 84,
         "job_exp": 42, "zeny": 210},
        {"kind": "rare_drop", "item_id": "poring_card", "item_name": "波利卡片", "qty": 1},
        {"kind": "retreat", "reason": "補品用盡", "seconds_survived": 3600},
    ]
    lines = event_lines(events)
    text = "\n".join(str(getattr(l, "plain", l)) for l in lines)
    assert "波利" in text and "42" in text
    assert "★" in text
    assert "補品用盡" in text


def test_inventory_table_lists_items_and_equipment():
    inv = {
        "items": {"red_potion": 10, "jellopy": 55},
        "equipment": [
            {"id": 1, "equipment_id": "knife", "refine": 7,
             "equipped_slot": "weapon", "card_ids": []}
        ],
    }
    out = _render(inventory_table(inv))
    assert "red_potion" in out and "10" in out
    assert "knife" in out and "+7" in out


def test_shop_table_and_hunt_summary():
    out = _render(shop_table({"items": [{"id": "red_potion", "name": "紅藥水", "price": 50, "kind": "consumable"}], "equipment": []}))
    assert "red_potion" in out and "50" in out
    summary = _render(hunt_summary({"kills": 12, "base_exp": 300, "job_exp": 100, "zeny": 500, "effective_seconds": 3600, "retreated": False, "drops": {"jellopy": 3}}))
    assert "12" in summary and "jellopy" in summary


def test_retreat_advice_known_and_unknown():
    assert "紅色藥水" in retreat_advice("補品用盡")
    assert retreat_advice("某個沒定義的原因") == "換個地方打打看，或先提升角色數值。"


def test_newbie_hint_panel_renders():
    out = _render(newbie_hint_panel())
    assert "新手指引" in out and "stats" in out


def test_hunt_summary_shows_retreat_reason():
    out = _render(hunt_summary({"kills": 0, "base_exp": 0, "job_exp": 0, "zeny": 0,
                                "effective_seconds": 100, "retreated": True,
                                "retreat_reason": "補品用盡"}))
    assert "補品用盡" in out


def test_event_lines_truncates_long_combat():
    events = [{"kind": "attack", "actor": "T", "target": "王", "damage": i,
              "crit": False, "hit": True} for i in range(60)]
    events.append({"kind": "challenge_result", "outcome": "win", "rounds": 60,
                   "base_exp": 100, "job_exp": 50, "zeny": 200, "exp_penalty": 0,
                   "drops": {}})
    lines = event_lines(events)
    text = "\n".join(str(getattr(l, "plain", l)) for l in lines)
    assert "省略 40 條" in text
    assert "挑戰結果：勝利" in text
    assert len(lines) == 22  # 10 + 省略 + 10 + result
