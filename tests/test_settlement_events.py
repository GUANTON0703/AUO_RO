from server.settlement import events as ev


def test_kill_batch_event():
    e = ev.KillBatchEvent(monster_name="波利", count=42, base_exp=84, job_exp=42, zeny=210)
    assert e.count == 42 and e.kind == "kill_batch"


def test_rare_drop_event():
    e = ev.RareDropEvent(item_id="poring_card", item_name="波利卡片", qty=1)
    assert e.kind == "rare_drop"


def test_potion_used_event():
    e = ev.PotionUsedEvent(item_id="red_potion", item_name="紅色藥水", count=23, remaining=12)
    assert e.kind == "potion_used"


def test_retreat_event():
    e = ev.RetreatEvent(reason="補品用盡", seconds_survived=7200)
    assert e.kind == "retreat"
