from server.combat import events as ev


def test_events_carry_actor_and_target():
    a = ev.AttackEvent(actor="玩家", target="波利", damage=42, crit=False, hit=True)
    assert a.damage == 42 and a.hit is True


def test_miss_event_has_zero_damage():
    m = ev.AttackEvent(actor="波利", target="玩家", damage=0, crit=False, hit=False)
    assert m.hit is False and m.damage == 0


def test_kill_event():
    k = ev.KillEvent(actor="玩家", target="波利")
    assert k.target == "波利"


def test_skill_event():
    s = ev.SkillEvent(actor="玩家", target="波利", skill_id="bash", skill_name="爆裂波動", damage=88)
    assert s.skill_id == "bash"


def test_heal_event():
    h = ev.HealEvent(actor="玩家", target="玩家", amount=30)
    assert h.amount == 30


def test_status_events():
    ap = ev.StatusAppliedEvent(actor="玩家", target="波利", status="poison", duration=3)
    ex = ev.StatusExpiredEvent(target="波利", status="poison")
    assert ap.status == "poison" and ex.status == "poison"


def test_all_events_have_kind_string():
    e = ev.AttackEvent(actor="a", target="b", damage=1, crit=False, hit=True)
    assert e.kind == "attack"
