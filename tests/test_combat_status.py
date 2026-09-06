from server.combat.combatant import Combatant
from server.combat.status import Status, tick_statuses, apply_status


def _dummy(**kw):
    base = dict(name="x", max_hp=100, max_sp=20, atk=50, matk=10, defense=0,
                mdef=0, hit=30, flee=30, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_dot_deals_damage_each_round_then_expires():
    c = _dummy()
    apply_status(c, Status(kind="dot", name="poison", duration=3, magnitude=8))
    events = []
    for _ in range(3):
        tick_statuses(c, events)
    assert c.hp == 100 - 24
    assert not c.statuses  # 3 回合後過期


def test_stat_mod_changes_effective_stat_while_active():
    c = _dummy(atk=50)
    apply_status(c, Status(kind="stat_mod", name="curse", duration=2, stat="atk", magnitude=-20))
    assert c.effective_atk == 30
    tick_statuses(c, [])
    tick_statuses(c, [])
    assert c.effective_atk == 50   # 過期還原


def test_stun_flag():
    c = _dummy()
    apply_status(c, Status(kind="stun", name="stun", duration=1, magnitude=0))
    assert c.stunned is True
    tick_statuses(c, [])
    assert c.stunned is False


def test_reapplying_status_refreshes_duration():
    c = _dummy()
    apply_status(c, Status(kind="dot", name="poison", duration=2, magnitude=5))
    tick_statuses(c, [])
    apply_status(c, Status(kind="dot", name="poison", duration=2, magnitude=5))
    assert [s for s in c.statuses if s.name == "poison"][0].duration == 2
