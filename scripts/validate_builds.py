"""各職畢業路線驗證：普通怪 clear 時間與中後期 MVP 王戰壓力。
band 目標：3~10 回合/隻（<2.5 = 太輾壓、>14 = 打不動）。
MVP 目標：同級畢業向配置約 30~80 回合；失敗會標出，方便調整裝備或數值。
"""
import io, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from server.content import load_content
from server.combat import simulate_fight
from server.combat.combatant import Combatant
from server.combat.grind import simulate_grind
from server.progression import CharacterSnapshot, EquippedPiece, build_player_combatant

c = load_content()

def hero(job, lv, stats, gear, learned):
    return build_player_combatant(CharacterSnapshot(
        name="P", job_id=job, base_level=lv, job_level=min(lv, 50),
        stats=stats, learned_skills=learned,
        equipped=[EquippedPiece(e[0], e[1], e[2]) for e in gear]), c)

def same_level_mob(lv, role="normal"):
    cand = sorted((m for m in c.monsters.values()
                   if abs(m.level - lv) <= 3 and m.role == role),
                  key=lambda m: abs(m.level - lv))
    return cand[0] if cand else None

def band(job, lv, stats, gear, learned, label):
    m = same_level_mob(lv)
    if not m:
        print(f"  {label:34} L{lv}: 無同級 normal 怪"); return
    tot = k = 0
    for i in range(10):
        r = simulate_grind(hero(job, lv, stats, gear, learned), m, n_fights=30, rng=random.Random(i))
        tot += r.total_rounds; k += r.kills
    rpk = tot / max(1, k)
    flag = "  [!] 太快(輾壓)" if rpk < 2.5 else ("  [!] 太慢(打不動)" if rpk > 14 else "")
    print(f"  {label:34} L{lv} vs {m.name:8}: {rpk:4.1f} 回合/隻{flag}")


def mvp_band(job, lv, stats, gear, learned, mvp):
    rounds = []
    wins = 0
    for seed in range(3):
        result = simulate_fight(
            hero(job, lv, stats, gear, learned),
            Combatant.from_monster(mvp),
            rng=random.Random(seed),
            max_rounds=400,
            flee_hp_frac=0.0,
        )
        rounds.append(result.rounds)
        wins += result.winner == "P"
    avg = sum(rounds) / len(rounds)
    flags = []
    if wins < len(rounds):
        flags.append("無法擊殺")
    if avg < 30:
        flags.append("太快")
    elif avg > 80:
        flags.append("太慢")
    flag = f"  [!] {'/'.join(flags)}" if flags else ""
    print(f"  {job:12} L{lv:2} vs {mvp.name:10}: {avg:4.1f} 回合{flag}")

MELEE = lambda lv: {"str": lv+10, "agi": lv//2, "vit": lv//2, "int": 5, "dex": lv//3, "luk": lv//4}
AGI  = lambda lv: {"str": lv//2, "agi": lv, "vit": lv//4, "int": 5, "dex": lv//3, "luk": lv//2}
CAST = lambda lv: {"str": 5, "agi": lv//4, "vit": lv//3, "int": lv+10, "dex": lv, "luk": 5}

CASES = [
 ("暴刺 (crit sin)", "assassin", AGI,
  lambda lv: [("main_gauche_4", 4, ["soldier_skeleton_card","desert_wolf_card"]),
              ("chain_mail_1", 4, []), ("boots", 4, ["matyr_card"])],
  {"katar_mastery": 5, "double_attack": 5, "sonic_blow": 5}),
 ("BB 騎士", "knight", MELEE,
  lambda lv: [("katana_4", 4, ["skel_worker_card","wolf_card","andre_card" if "andre_card" in c.cards else "skeleton_card","skeleton_card"]),
              ("full_plate_1" if lv >= 50 else "chain_mail_1", 4, []), ("boots", 4, ["matyr_card"])],
  {"bash": 5, "sword_mastery": 5, "bowling_bash": 5, "twohand_quicken": 5}),
 ("DS 獵人", "hunter", AGI,
  lambda lv: [("composite_bow_4", 4, ["skel_worker_card","minorous_horn_card","desert_wolf_card","archer_skeleton_card"]),
              ("tights_1", 4, []), ("boots", 4, ["matyr_card"])],
  {"double_strafe": 5, "owls_eye": 5, "improve_concentration": 5, "true_sight": 5}),
 ("火巫師", "wizard", CAST,
  lambda lv: [("staff", 4, []), ("chain_mail_1", 4, []), ("boots", 4, [])],
  {"fire_bolt": 5, "meteor_storm": 5, "amplify_magic": 5, "increase_sp": 5}),
 ("戰鐵匠", "blacksmith", MELEE,
  lambda lv: [("orcish_axe_4", 4, ["skel_worker_card","minorous_horn_card","skeleton_card","skeleton_card"]),
              ("full_plate_1" if lv >= 50 else "chain_mail_1", 4, []), ("boots", 4, ["matyr_card"])],
  {"smith_mastery": 5, "adrenaline_rush": 5, "over_thrust": 5, "power_thrust": 5, "weapon_perfection": 5}),
]

for label, job, statf, gearf, learned in CASES:
    print(label)
    for lv in (20, 40, 60):
        try:
            band(job, lv, statf(lv), [g for g in gearf(lv) if g[0] in c.equipment], learned,
                 f"L{lv} 畢業裝")
        except Exception as e:
            print(f"  L{lv}: ERROR {e}")

print("MVP 王戰（只驗證中後期，seed=0..2 平均）")
for label, job, statf, gearf, learned in CASES:
    print(label)
    for mvp in sorted((m for m in c.mvps.values() if m.level >= 45),
                      key=lambda m: (m.level, m.id)):
        try:
            mvp_band(job, mvp.level, statf(mvp.level),
                     [g for g in gearf(mvp.level) if g[0] in c.equipment],
                     learned, mvp)
        except Exception as e:
            print(f"  {mvp.id}: ERROR {e}")
