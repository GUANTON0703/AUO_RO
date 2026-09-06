from shared.models import AccountPublic, CharacterPublic, JobId


def test_job_id_has_novice_and_six_first_jobs():
    assert JobId.NOVICE.value == "novice"
    first_jobs = {"swordman", "mage", "archer", "acolyte", "merchant", "thief"}
    assert first_jobs <= {j.value for j in JobId}


def test_character_public_round_trips():
    c = CharacterPublic(
        id=1, name="小明", job_id=JobId.NOVICE, base_level=1, job_level=1,
        base_exp=0, job_exp=0, stat_str=1, stat_agi=1, stat_vit=1,
        stat_int=1, stat_dex=1, stat_luk=1, stat_points=0, skill_points=0,
        zeny=0, location_map="prontera_east_gate",
    )
    assert CharacterPublic.model_validate(c.model_dump()) == c


def test_account_public_hides_password():
    a = AccountPublic(id=1, username="u")
    assert "password" not in a.model_dump()
