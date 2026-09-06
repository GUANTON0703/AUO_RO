import copy
import random
from dataclasses import dataclass

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from shared.content import MonsterDef


@dataclass
class FightProfile:
    avg_rounds: float
    avg_damage_taken: float
    win_rate: float


def estimate_fight_profile(player: Combatant, monster: MonsterDef,
                           rng: random.Random, samples: int = 20) -> FightProfile:
    rounds = dmg = 0.0
    wins = 0
    for _ in range(samples):
        p = copy.deepcopy(player)
        p.hp, p.sp = p.max_hp, p.max_sp
        for s in p.skills:
            s._cd_left = 0
        foe = Combatant.from_monster(monster)
        r = simulate_fight(p, foe, rng)
        rounds += r.rounds
        dmg += max(0, p.max_hp - p.hp)
        if r.winner == p.name:
            wins += 1
    return FightProfile(rounds / samples, dmg / samples, wins / samples)
