import random

from server.settlement.config import HuntConfig
from shared.content import DropEntry


def roll_drops(entries: list[DropEntry], kills: int, rng: random.Random,
               offline: bool, pity_in: dict, cfg: HuntConfig) -> tuple[dict, dict]:
    got: dict = {}
    pity = dict(pity_in)
    threshold = cfg.card_pity_threshold

    for e in entries:
        avg_qty = (e.min_qty + e.max_qty) / 2
        is_rare = e.rate < cfg.rare_drop_cutoff

        if not is_rare:
            rate = min(1.0, e.rate * cfg.drop_multiplier)
            if offline:
                qty = round(kills * rate * avg_qty)
            else:
                qty = sum(rng.randint(e.min_qty, e.max_qty)
                          for _ in range(kills) if rng.random() < rate)
            if qty:
                got[e.item_id] = got.get(e.item_id, 0) + qty
            continue

        # 稀有掉落：擲骰 + 保底計數器
        if kills <= 0:
            hits = 0
        elif offline:
            hits = rng.binomialvariate(kills, min(1.0, e.rate * cfg.drop_multiplier)) if e.rate > 0 else 0
        else:
            rate = min(1.0, e.rate * cfg.drop_multiplier)
            hits = sum(1 for _ in range(kills) if rng.random() < rate)

        counter = pity.get(e.item_id, 0) + kills
        if hits > 0:
            forced = 0
            counter = 0
        else:
            forced = counter // threshold
            counter = counter % threshold

        total = hits + forced
        if total:
            got[e.item_id] = got.get(e.item_id, 0) + total
        pity[e.item_id] = counter

    return got, pity
