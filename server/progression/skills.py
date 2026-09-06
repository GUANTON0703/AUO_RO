def skill_points_available(job_level: int, learned: dict, carried: int = 0) -> int:
    return (job_level - 1) + carried - sum(learned.values())


def can_learn(content, character_job: str, skill_id: str, target_level: int,
              current_learned: dict, points_available: int) -> tuple[bool, str]:
    skill = content.skills.get(skill_id)
    if skill is None:
        return False, "技能不存在"
    if skill.job_id != character_job:
        return False, "非本職技能"
    if target_level < 1 or target_level > skill.max_level:
        return False, "技能等級超出範圍"
    have = current_learned.get(skill_id, 0)
    if target_level <= have:
        return False, "已達或超過該等級"
    if target_level - have > points_available:
        return False, "技能點不足"
    return True, ""
