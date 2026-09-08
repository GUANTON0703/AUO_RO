from shared.models import AccountPublic, CharacterPublic


def test_character_public_accepts_any_job_id():
    for job in ("novice", "thief", "assassin"):
        assert CharacterPublic(
            id=1, name="x", job_id=job, base_level=1, job_level=1,
            base_exp=0, job_exp=0, stat_str=1, stat_agi=1, stat_vit=1,
            stat_int=1, stat_dex=1, stat_luk=1, stat_points=0, skill_points=0,
            zeny=0, location_map="prontera_east_gate",
        ).job_id == job


def test_character_public_round_trips():
    c = CharacterPublic(
        id=1, name="小明", job_id="novice", base_level=1, job_level=1,
        base_exp=0, job_exp=0, stat_str=1, stat_agi=1, stat_vit=1,
        stat_int=1, stat_dex=1, stat_luk=1, stat_points=0, skill_points=0,
        zeny=0, location_map="prontera_east_gate",
    )
    assert CharacterPublic.model_validate(c.model_dump()) == c


def test_account_public_hides_password():
    a = AccountPublic(id=1, username="u")
    assert "password" not in a.model_dump()
