import random
from dataclasses import dataclass

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from shared.content import MonsterDef


@dataclass
class GrindResult:
    kills: int
    base_exp: int
    job_exp: int
    total_rounds: int
    damage_taken: int
    player_defeated: bool
    fights_attempted: int


def simulate_grind(player: Combatant, monster_def: MonsterDef, n_fights: int,
                   rng: random.Random) -> GrindResult:
    kills = base_exp = job_exp = total_rounds = damage_taken = 0
    defeated = False
    attempted = 0
    for _ in range(n_fights):
        attempted += 1
        hp_before = player.hp
        foe = Combatant.from_monster(monster_def)
        # 清掉上一場殘留的 debuff/CD
        player.statuses = [s for s in player.statuses if s.kind != "dot"]
        for s in player.skills:
            s._cd_left = 0
        result = simulate_fight(player, foe, rng)
        total_rounds += result.rounds
        damage_taken += max(0, hp_before - player.hp)
        if result.winner == player.name:
            kills += 1
            base_exp += monster_def.base_exp
            job_exp += monster_def.job_exp
        else:
            defeated = True
            break
    return GrindResult(kills, base_exp, job_exp, total_rounds, damage_taken,
                       defeated, attempted)
