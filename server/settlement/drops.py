import random
import sqlite3
from dataclasses import dataclass, field

from server.db import connection
from server.settlement.config import HuntConfig
from shared.content import DropEntry


@dataclass(frozen=True)
class DropRateOverrides:
    global_rates: dict[str, float] = field(default_factory=dict)
    source_rates: dict[tuple[str, str], float] = field(default_factory=dict)


def load_drop_rate_overrides() -> DropRateOverrides:
    """讀取目前 GM 覆寫；資料庫尚未初始化時退回空設定。"""
    try:
        with connection.get_connection() as conn:
            global_rates = {
                row["item_id"]: float(row["rate"])
                for row in conn.execute("SELECT item_id, rate FROM global_drop_rates")
            }
            source_rates = {
                (row["source_id"], row["item_id"]): float(row["rate"])
                for row in conn.execute(
                    "SELECT source_id, item_id, rate FROM source_drop_rates"
                )
            }
    except (OSError, RuntimeError, sqlite3.Error):
        return DropRateOverrides()
    return DropRateOverrides(global_rates=global_rates, source_rates=source_rates)


def effective_drop_rate(source_id: str | None, item_id: str, content_rate: float,
                        overrides: DropRateOverrides | None = None) -> float:
    """來源專屬 > 全域物品 > content 原始值；0 也是有效覆寫值。"""
    overrides = overrides or load_drop_rate_overrides()
    if source_id is not None:
        source_rate = overrides.source_rates.get((source_id, item_id))
        if source_rate is not None:
            return source_rate
    global_rate = overrides.global_rates.get(item_id)
    return content_rate if global_rate is None else global_rate


def roll_drops(entries: list[DropEntry], kills: int, rng: random.Random,
               offline: bool, pity_in: dict, cfg: HuntConfig, *,
               source_id: str | None = None,
               overrides: DropRateOverrides | None = None) -> tuple[dict, dict]:
    got: dict = {}
    pity = dict(pity_in)
    threshold = cfg.card_pity_threshold
    overrides = overrides or load_drop_rate_overrides()

    for e in entries:
        avg_qty = (e.min_qty + e.max_qty) / 2
        is_rare = e.rate < cfg.rare_drop_cutoff
        effective_rate = effective_drop_rate(source_id, e.item_id, e.rate, overrides)

        if not is_rare:
            rate = min(1.0, effective_rate * cfg.drop_multiplier)
            if offline:
                qty = round(kills * rate * avg_qty)
            else:
                qty = sum(rng.randint(e.min_qty, e.max_qty)
                          for _ in range(kills) if rng.random() < rate)
            if qty:
                got[e.item_id] = got.get(e.item_id, 0) + qty
            continue

        # 稀有掉落：擲骰 + 保底計數器
        zero_override = (
            effective_rate == 0.0
            and (
                (source_id, e.item_id) in overrides.source_rates
                or e.item_id in overrides.global_rates
            )
        )
        if zero_override:
            # GM 的 0 是明確停用，不讓既有 pity 強制給掉落；保留計數，
            # 之後恢復機率時仍可接續原本的保底進度。
            pity[e.item_id] = pity.get(e.item_id, 0) + kills
            continue
        if kills <= 0:
            hits = 0
        elif offline:
            rate = min(1.0, effective_rate * cfg.drop_multiplier)
            hits = rng.binomialvariate(kills, rate) if rate > 0 else 0
        else:
            rate = min(1.0, effective_rate * cfg.drop_multiplier)
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
