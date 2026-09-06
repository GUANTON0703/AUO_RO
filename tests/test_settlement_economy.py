from server.settlement.economy import zeny_per_kill
from server.content import load_content


def test_zeny_scales_with_level():
    c = load_content()
    lo = zeny_per_kill(c.get_monster("green_cotton_worm"))
    hi = zeny_per_kill(c.get_monster("wolf"))
    assert 0 < lo < hi


def test_zeny_is_int():
    c = load_content()
    assert isinstance(zeny_per_kill(c.get_monster("poring")), int)
