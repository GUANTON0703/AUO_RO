"""屬性相剋 / 抗性 / 種族加傷——戰鬥固有規則，跟 formulas 同層。"""

_chart = None


def _table() -> dict:
    global _chart
    if _chart is None:
        from server.content import load_content
        _chart = load_content().element_chart.table
    return _chart


def element_multiplier(attack_element: str, defender_element: str) -> float:
    row = _table().get(attack_element or "neutral", {})
    return row.get(defender_element or "neutral", 1.0)


def damage_mods(attacker, defender, attack_element: str | None) -> tuple[float, int, int]:
    """回 (相剋倍率, 目標對此屬性的抗性%, 攻擊方對目標種族的加傷%)。"""
    elem = attack_element or getattr(attacker, "attack_element", "neutral") or "neutral"
    mult = element_multiplier(elem, getattr(defender, "element", "neutral"))
    resist = getattr(defender, "element_resist", {}).get(elem, 0)
    race = getattr(attacker, "race_bonus", {}).get(
        getattr(defender, "race", "formless"), 0)
    race += getattr(attacker, "size_bonus", {}).get(
        getattr(defender, "size", "medium"), 0)
    return mult, resist, race
