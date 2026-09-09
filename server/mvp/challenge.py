import random
from dataclasses import asdict, dataclass, field, is_dataclass

from server.combat import simulate_fight
from server.combat.combatant import Combatant
from server.progression.levels import base_exp_for_next
from server.settlement.economy import zeny_per_kill
from server.settlement.drops import effective_drop_rate, load_drop_rate_overrides


@dataclass
class ChallengeConfig:
    flee_hp_frac: float = 0.15
    loss_exp_penalty_frac: float = 0.015
    mvp_drop_multiplier: float = 3.0
    win_zeny_multiplier: int = 5


@dataclass
class ChallengeResult:
    outcome: str          # win / loss / fled
    rounds: int
    base_exp: int = 0
    job_exp: int = 0
    zeny: int = 0
    exp_penalty: int = 0
    drops: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


def _event_dict(e) -> dict:
    return asdict(e) if is_dataclass(e) else dict(e)


def challenge_mvp(player: Combatant, mvp, cfg: ChallengeConfig, rng: random.Random,
                  player_base_level: int = 1) -> ChallengeResult:
    foe = Combatant.from_monster(mvp)
    fight = simulate_fight(player, foe, rng, max_rounds=400,
                           flee_hp_frac=cfg.flee_hp_frac)

    if fight.winner == player.name:
        outcome = "win"
    elif fight.outcome == "fled":
        outcome = "fled"
    else:
        outcome = "loss"

    events = [_event_dict(e) for e in fight.events]

    result = ChallengeResult(outcome=outcome, rounds=fight.rounds, events=events)

    if outcome == "win":
        drops: dict = {}
        overrides = load_drop_rate_overrides()
        for d in mvp.drops:
            content_rate = effective_drop_rate(mvp.id, d.item_id, d.rate, overrides)
            rate = min(1.0, content_rate * cfg.mvp_drop_multiplier)
            if rng.random() < rate:
                drops[d.item_id] = drops.get(d.item_id, 0) + rng.randint(d.min_qty, d.max_qty)
        result.drops = drops
        result.base_exp = mvp.base_exp
        result.job_exp = mvp.job_exp
        result.zeny = zeny_per_kill(mvp) * cfg.win_zeny_multiplier
    elif outcome == "loss":
        result.exp_penalty = round(
            base_exp_for_next(player_base_level) * cfg.loss_exp_penalty_frac
        )

    events.append({
        "kind": "challenge_result",
        "outcome": outcome,
        "rounds": fight.rounds,
        "base_exp": result.base_exp,
        "job_exp": result.job_exp,
        "zeny": result.zeny,
        "exp_penalty": result.exp_penalty,
        "drops": result.drops,
    })
    return result
