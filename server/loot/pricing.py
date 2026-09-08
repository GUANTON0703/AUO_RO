"""NPC 收購價。卡片以外的道具 / 裝備都能賣；沒設 npc_sell 就給保底價。"""

_RARITY_SELL = {"common": 60, "fine": 600, "legendary": 3500}


def equip_sell_price(eq) -> int:
    if eq.npc_sell:
        return eq.npc_sell
    if eq.npc_buy:
        return eq.npc_buy // 2
    return _RARITY_SELL.get(eq.rarity, 60)


def item_sell_price(item) -> int:
    if item.npc_sell:
        return item.npc_sell
    if item.npc_buy:
        return max(1, item.npc_buy // 2)
    return 1
