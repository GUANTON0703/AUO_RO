from server.loot import crafting


class _Recipe:
    def __init__(self, base_success_pct, required_craft_level):
        self.base_success_pct = base_success_pct
        self.required_craft_level = required_craft_level


def test_success_rate_scales_with_craft_level():
    r = _Recipe(base_success_pct=60, required_craft_level=2)
    assert crafting.success_rate(r, craft_level=2) == 60
    assert crafting.success_rate(r, craft_level=4) == 70    # +5% 每高一級
    assert crafting.success_rate(r, craft_level=1) == 55    # 低於門檻也會扣，不是直接鎖死
    assert crafting.success_rate(r, craft_level=99) == 95   # 封頂
    assert crafting.success_rate(_Recipe(10, 20), craft_level=1) == 5  # 下限


def test_mastery_bonus_stacks_separately_and_caps():
    r = _Recipe(base_success_pct=50, required_craft_level=1)
    assert crafting.mastery_bonus_pct(0) == 0
    assert crafting.mastery_bonus_pct(4) == 0
    assert crafting.mastery_bonus_pct(5) == 1
    assert crafting.mastery_bonus_pct(24) == 4
    assert crafting.mastery_bonus_pct(999) == crafting.MASTERY_CAP_PCT
    assert crafting.success_rate(r, craft_level=1, mastery_attempts=5) == 51
    assert crafting.success_rate(r, craft_level=1, mastery_attempts=999) == 50 + crafting.MASTERY_CAP_PCT


def test_apply_craft_exp_levels_up_and_caps():
    level, exp = crafting.apply_craft_exp(1, 0, crafting.craft_exp_for_next(1))
    assert level == 2 and exp == 0
    level, exp = crafting.apply_craft_exp(9, 0, 10_000)
    assert level == crafting.CRAFT_LEVEL_CAP
    assert exp == 0
