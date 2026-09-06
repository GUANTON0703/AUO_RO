from dataclasses import dataclass, field

from server.combat.combatant import Combatant, ResolvedSkill


@dataclass
class CharacterSnapshot:
    name: str
    job_id: str
    base_level: int
    job_level: int
    stats: dict
    learned_skills: dict = field(default_factory=dict)
    equipped_item_ids: list = field(default_factory=list)
    socketed_card_ids: list = field(default_factory=list)
    hp: int | None = None
    sp: int | None = None


def _sum_equipment_stats(content, item_ids: list) -> dict:
    acc: dict = {}
    for iid in item_ids:
        eq = content.equipment.get(iid)
        if not eq:
            continue
        for k, v in eq.stats.items():
            acc[k] = acc.get(k, 0) + v
    return acc


def _apply_card_effects(content, card_ids: list, out: dict) -> None:
    for cid in card_ids:
        card = content.cards.get(cid)
        if not card:
            continue
        for eff in card.effects:
            t = eff.get("type")
            if t == "flat_stat":
                out[eff["stat"]] = out.get(eff["stat"], 0) + eff["amount"]
            elif t == "percent_stat":
                base = out.get(eff["stat"], 0)
                out[eff["stat"]] = round(base * (1 + eff["pct"] / 100))
            # element_resist / race_damage / proc：戰鬥引擎 v1 尚未支援，略過


def _passive_stat_bonus(content, learned: dict) -> dict:
    bonus: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "passive":
            continue
        for eff in sk.effects:
            if eff.get("type") == "passive_stat":
                seq = eff.get("amount", [0])
                val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
                bonus[eff["stat"]] = bonus.get(eff["stat"], 0) + val
    return bonus


def build_player_combatant(snap: CharacterSnapshot, content) -> Combatant:
    job = content.get_job(snap.job_id)
    s = snap.stats
    STR, AGI, VIT, INT, DEX, LUK = (s["str"], s["agi"], s["vit"], s["int"], s["dex"], s["luk"])

    eq = _sum_equipment_stats(content, snap.equipped_item_ids)
    passives = _passive_stat_bonus(content, snap.learned_skills)

    max_hp = round(40 + snap.base_level * job.hp_per_level * (1 + VIT / 100))
    max_sp = round(11 + snap.base_level * job.sp_per_level * (1 + INT / 100))
    atk = STR + (STR // 10) ** 2 + DEX // 5 + LUK // 5 + eq.get("atk", 0) + passives.get("atk", 0)
    matk = INT + (INT // 7) ** 2 + eq.get("matk", 0) + passives.get("matk", 0)
    defense = min(95, eq.get("def", 0) + VIT // 2 + passives.get("defense", 0))
    mdef = min(95, eq.get("mdef", 0) + INT // 2)
    hit = snap.base_level + DEX + eq.get("hit", 0)
    flee = snap.base_level + AGI + eq.get("flee", 0)
    aspd = min(193, round(100 + AGI * 0.7 + DEX * 0.15 + eq.get("aspd", 0)))
    crit = round(LUK / 3) + eq.get("crit", 0)

    derived = {"max_hp": max_hp, "max_sp": max_sp, "atk": atk, "matk": matk,
               "defense": defense, "mdef": mdef, "hit": hit, "flee": flee,
               "crit": crit}
    _apply_card_effects(content, snap.socketed_card_ids, derived)

    resolved = []
    for sid, lvl in snap.learned_skills.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        sp_cost = sk.sp_cost[min(lvl, len(sk.sp_cost)) - 1] if sk.sp_cost else 0
        resolved.append(ResolvedSkill(
            skill_id=sid, name=sk.name, level=lvl, kind="active",
            sp_cost=sp_cost, cooldown_rounds=round(sk.cooldown_s / 2),
            effects=sk.effects, trigger=idle.get("trigger", "every_turn"),
            priority=idle.get("priority", 1),
        ))

    return Combatant(
        name=snap.name, max_hp=derived["max_hp"], max_sp=derived["max_sp"],
        atk=max(0, derived["atk"]), matk=max(0, derived["matk"]),
        defense=max(0, min(95, derived["defense"])), mdef=max(0, min(95, derived["mdef"])),
        hit=max(0, derived["hit"]), flee=max(0, derived["flee"]),
        aspd=max(1, min(193, aspd)), crit=max(0, derived["crit"]),
        is_caster=(derived["matk"] > derived["atk"]),
        skills=resolved,
        hp=snap.hp if snap.hp is not None else 0,
        sp=snap.sp if snap.sp is not None else 0,
    )
