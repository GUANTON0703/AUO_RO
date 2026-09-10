from dataclasses import dataclass, field

from server.combat.combatant import Combatant, ResolvedSkill
from server.loot import refine as refine_mod

# 武器類別 → (攻擊主屬性, 基礎攻速, 爆擊率倍率)。對齊 Pre-Renewal RO 的手感：
# 短劍/拳刃最快、雙手武器最慢、弓吃 DEX、法杖走 MATK。
WEAPON_PROFILE = {
    "dagger":  ("str", 135, 1.0),
    "sword":   ("str", 125, 1.0),
    "axe":     ("str", 116, 1.0),
    "mace":    ("str", 120, 1.0),
    "twohand": ("str", 108, 1.0),
    "katar":   ("str", 130, 1.6),   # 拳刃爆擊率提高（刺客爆擊流核心）
    "bow":     ("dex", 122, 1.0),
    "staff":   ("str", 112, 1.0),   # 法師靠 MATK，物理攻擊本來就低
}
_DEFAULT_WEAPON = ("str", 118, 1.0)


@dataclass
class EquippedPiece:
    equipment_id: str
    refine: int = 0
    card_ids: list = field(default_factory=list)


@dataclass
class CharacterSnapshot:
    name: str
    job_id: str
    base_level: int
    job_level: int
    stats: dict
    learned_skills: dict = field(default_factory=dict)
    equipped: list = field(default_factory=list)
    primary_skill_id: str | None = None
    skill_toggles: dict = field(default_factory=dict)
    hp: int | None = None
    sp: int | None = None


def _sum_equipment_stats(content, pieces: list) -> dict:
    acc: dict = {}
    for piece in pieces:
        eq = content.equipment.get(piece.equipment_id)
        if not eq:
            continue
        bonus = refine_mod.refine_stat_bonus(eq.stats, piece.refine)
        for k, v in eq.stats.items():
            acc[k] = acc.get(k, 0) + v + bonus.get(k, 0)
    return acc


def _card_flat_stats(content, pieces: list) -> dict:
    """卡片的 flat_stat 貢獻，回傳跟裝備一樣的扁平 stat 池
    （str/agi/…/atk/defense/aspd/crit/max_hp…），在 STR→衍生數值計算之前併進去。"""
    acc: dict = {}
    for piece in pieces:
        for cid in piece.card_ids:
            card = content.cards.get(cid)
            if not card:
                continue
            for eff in card.effects:
                if eff.get("type") == "flat_stat":
                    acc[eff["stat"]] = acc.get(eff["stat"], 0) + eff["amount"]
    return acc


def _apply_card_effects(content, pieces: list, derived: dict) -> dict:
    """percent_stat 套進已算好的 derived，並回傳戰鬥用的 {resist, race, size, atk_element}。
    flat_stat 已在 _card_flat_stats 處理；附魔卡（weapon_element）只有鑲在武器上才算。"""
    combat = {"resist": {}, "race": {}, "size": {}, "atk_element": None}
    for piece in pieces:
        eq = content.equipment.get(piece.equipment_id)
        slot = eq.slot if eq else None
        for cid in piece.card_ids:
            card = content.cards.get(cid)
            if not card:
                continue
            for eff in card.effects:
                t = eff.get("type")
                if t == "percent_stat":
                    base = derived.get(eff["stat"], 0)
                    derived[eff["stat"]] = round(base * (1 + eff["pct"] / 100))
                elif t == "element_resist":
                    combat["resist"][eff["element"]] = (
                        combat["resist"].get(eff["element"], 0) + eff["pct"])
                elif t == "race_damage":
                    combat["race"][eff["race"]] = (
                        combat["race"].get(eff["race"], 0) + eff["pct"])
                elif t == "size_damage":
                    combat["size"][eff["size"]] = (
                        combat["size"].get(eff["size"], 0) + eff["pct"])
                elif t == "weapon_element" and slot == "weapon":
                    combat["atk_element"] = eff["element"]
                # on_hit_proc：走技能路線的 proc，卡片 proc 暫不支援
    return combat


def _passive_procs(content, learned: dict) -> dict:
    """被動技能的觸發機率 {effect: 機率%}（例：double_attack → {extra_hit: 25}）。"""
    out: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "passive":
            continue
        for eff in sk.effects:
            if eff.get("type") != "proc":
                continue
            seq = eff.get("chance_pct", [0])
            val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
            key = eff.get("effect", "")
            out[key] = max(out.get(key, 0), val)
    return out


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
    eq = _sum_equipment_stats(content, snap.equipped)
    for k, v in _card_flat_stats(content, snap.equipped).items():
        eq[k] = eq.get(k, 0) + v
    STR, AGI, VIT, INT, DEX, LUK = (
        s["str"] + eq.get("str", 0), s["agi"] + eq.get("agi", 0),
        s["vit"] + eq.get("vit", 0), s["int"] + eq.get("int", 0),
        s["dex"] + eq.get("dex", 0), s["luk"] + eq.get("luk", 0))

    passives = _passive_stat_bonus(content, snap.learned_skills)

    # HP/SP 隨等級加速成長（配合怪物 HP 公式的 level² 項），玩家才打得動同級怪
    lv = snap.base_level
    max_hp = round((40 + lv * job.hp_per_level * (1.5 + lv / 12)) * (1 + VIT / 60))
    max_sp = round((11 + lv * job.sp_per_level * (1.2 + lv / 25)) * (1 + INT / 80))
    weapon = next((content.equipment.get(p.equipment_id) for p in snap.equipped
                   if content.equipment.get(p.equipment_id)
                   and content.equipment[p.equipment_id].slot == "weapon"), None)
    wt = weapon.weapon_type if weapon else None
    atk_stat, base_aspd, crit_rate_mult = WEAPON_PROFILE.get(wt, _DEFAULT_WEAPON)
    # 攻擊主屬性照武器類型（原版 RO：近戰 STR、弓 DEX、法杖走 MATK）
    _pool = {"str": STR, "dex": DEX}
    atk_main = _pool.get(atk_stat, STR)
    atk_sub = DEX if atk_stat == "str" else STR
    # 原版：武器攻擊 × (1 + 主屬性/200)，其他攻擊來源（卡片/飾品）不吃這個加成
    weapon_atk = weapon.stats.get("atk", 0) if weapon else 0
    scaled_weapon = weapon_atk * (1 + atk_main / 200)
    atk = round((atk_main + (atk_main // 10) ** 2 + atk_sub // 5 + LUK // 5
                 + scaled_weapon + (eq.get("atk", 0) - weapon_atk)
                 + passives.get("atk", 0)) * (1 + lv / 50))
    matk = round((INT + (INT // 7) ** 2 + eq.get("matk", 0)
                  + passives.get("matk", 0)) * (1 + lv / 50))
    defense = min(400, eq.get("defense", 0) + VIT // 2 + passives.get("defense", 0))
    mdef = min(400, eq.get("mdef", 0) + INT // 2 + passives.get("mdef", 0))
    hit = snap.base_level + DEX + LUK // 3 + eq.get("hit", 0) + passives.get("hit", 0)
    flee = snap.base_level + AGI + LUK // 5 + eq.get("flee", 0) + passives.get("flee", 0)
    aspd = min(193, round(base_aspd + AGI * 0.55 + DEX * 0.12 + eq.get("aspd", 0)
                          + passives.get("aspd", 0)))
    crit = round(LUK * 0.3 * crit_rate_mult) + eq.get("crit", 0) + passives.get("crit", 0)
    # 施法後延遲：DEX 高 = 可連續放招（原版高 DEX 幾乎無延遲）
    cast_delay = 0 if DEX >= 100 else (1 if DEX >= 45 else 2)
    max_hp += passives.get("max_hp", 0) + eq.get("max_hp", 0)
    max_sp += passives.get("max_sp", 0) + eq.get("max_sp", 0)

    derived = {"max_hp": max_hp, "max_sp": max_sp, "atk": atk, "matk": matk,
               "defense": defense, "mdef": mdef, "hit": hit, "flee": flee,
               "crit": crit}
    combat_mods = _apply_card_effects(content, snap.equipped, derived)

    # 攻擊屬性：武器本身屬性 → 附魔卡覆蓋
    attack_element = combat_mods["atk_element"] or (
        weapon.element if weapon else "neutral")
    crit_mult = 1.6 if (weapon and weapon.weapon_type == "katar") else 1.4

    resolved = []
    for sid, lvl in snap.learned_skills.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        if not snap.skill_toggles.get(sid, idle.get("enabled", True)):
            continue   # 玩家關掉的、或預設就不掛機放的技能
        sp_cost = sk.sp_cost[min(lvl, len(sk.sp_cost)) - 1] if sk.sp_cost else 0
        priority = idle.get("priority", 1)
        if sid == snap.primary_skill_id:
            priority = 99   # 指定主攻 → 蓋過其他攻擊技
        resolved.append(ResolvedSkill(
            skill_id=sid, name=sk.name, level=lvl, kind="active",
            sp_cost=sp_cost, cooldown_rounds=round(sk.cooldown_s / 2),
            effects=sk.effects, trigger=idle.get("trigger", "every_turn"),
            priority=priority,
        ))

    return Combatant(
        name=snap.name, max_hp=derived["max_hp"], max_sp=derived["max_sp"],
        atk=max(0, derived["atk"]), matk=max(0, derived["matk"]),
        defense=max(0, min(400, derived["defense"])), mdef=max(0, min(400, derived["mdef"])),
        hit=max(0, derived["hit"]), flee=max(0, derived["flee"]),
        aspd=max(1, min(193, aspd)), crit=max(0, derived["crit"]),
        is_caster=(derived["matk"] > derived["atk"]),
        crit_mult=crit_mult,
        cast_delay=cast_delay,
        soft_def=VIT // 3, soft_mdef=INT // 4,
        skills=resolved,
        attack_element=attack_element,
        element_resist=combat_mods["resist"],
        race_bonus=combat_mods["race"],
        size_bonus=combat_mods["size"],
        procs=_passive_procs(content, snap.learned_skills),
        # 換裝後 max 可能變小，把續戰的 hp/sp 夾回上限
        hp=min(snap.hp, derived["max_hp"]) if snap.hp is not None else 0,
        sp=min(snap.sp, derived["max_sp"]) if snap.sp is not None else 0,
    )
