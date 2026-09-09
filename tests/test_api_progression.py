def _make_char(client, headers, name="勇者"):
    return client.post("/api/characters", headers=headers, json={"name": name}).json()


def test_allocate_stats(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/stats", headers=headers,
                    json={"str": 3})
    assert r.status_code == 200
    assert r.json()["stat_str"] == 4


def test_allocate_stats_rejects_insufficient_points(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/stats", headers=headers,
                    json={"str": 99})
    assert r.status_code == 400


def test_learn_skill_requires_job_and_points(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                    json={"skill_id": "bash", "level": 1})
    assert r.status_code == 400


def test_jobchange_gated_on_job_level(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "swordman"})
    assert r.status_code == 400


def test_jobchange_succeeds_at_job_10(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    db_helpers.set_job_level(ch["id"], 10)
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "swordman"})
    assert r.status_code == 200
    assert r.json()["job_id"] == "swordman"
    assert r.json()["job_level"] == 1


def test_learn_skill_after_jobchange(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    db_helpers.set_job_level(ch["id"], 10)
    client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                json={"target_job_id": "swordman"})
    db_helpers.set_job_level(ch["id"], 5)
    r = client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                    json={"skill_id": "bash", "level": 3})
    assert r.status_code == 200
    assert r.json()["learned_skills"]["bash"] == 3


def test_reset_stats_refunds_points(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "重來"}).json()
    db_helpers.set_base_level(ch["id"], 20)
    client.post(f"/api/characters/{ch['id']}/stats", headers=h, json={"str": 10})
    r = client.post(f"/api/characters/{ch['id']}/resetstats", headers=h)
    assert r.status_code == 200
    assert r.json()["stat_str"] == 1
    r2 = client.post(f"/api/characters/{ch['id']}/stats", headers=h, json={"str": 10})
    assert r2.status_code == 200


def test_reset_skills_clears_learned(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "忘招"}).json()
    db_helpers.set_job(ch["id"], "swordman", 10, 0)
    client.post(f"/api/characters/{ch['id']}/skills", headers=h, json={"skill_id": "bash", "level": 3})
    r = client.post(f"/api/characters/{ch['id']}/resetskills", headers=h)
    assert r.status_code == 200
    r2 = client.post(f"/api/characters/{ch['id']}/skills", headers=h, json={"skill_id": "bash", "level": 5})
    assert r2.status_code == 200


def test_second_jobchange_thief_to_assassin_at_job_40(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    db_helpers.set_job_level(ch["id"], 10)
    client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                json={"target_job_id": "thief"})
    db_helpers.set_job_level(ch["id"], 40)
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "assassin"})
    assert r.status_code == 200, r.json()
    assert r.json()["job_id"] == "assassin"


def test_second_job_keeps_first_job_skill_points(client, auth, db_helpers):
    """二轉後：一轉練的等級要帶進來，才不會學不了二轉技能。"""
    _, headers, _ = auth
    ch = _make_char(client, headers)
    db_helpers.set_job_level(ch["id"], 10)
    client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                json={"target_job_id": "thief"})
    # 一轉練滿並把技能點花在賊技能上
    db_helpers.set_job_level(ch["id"], 40)
    for sid in ("double_attack", "steal", "envenom"):
        client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                    json={"skill_id": sid, "level": 5})
    # 二轉
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "assassin"})
    assert r.status_code == 200
    assert r.json()["job_level"] == 1
    # 二轉後應該還有可用技能點（一轉的 39 級 - 已花 15 = 24），不是負的
    assert r.json()["skill_points"] >= 20, r.json()
    # 而且真的學得起來二轉技能
    lr = client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                     json={"skill_id": "katar_mastery", "level": 3})
    assert lr.status_code == 200, lr.json()


def test_second_job_can_relearn_full_ancestry_after_skill_reset(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _make_char(client, headers, name="重修刺客")

    db_helpers.set_job_level(ch["id"], 10)
    r = client.post(
        f"/api/characters/{ch['id']}/jobchange",
        headers=headers,
        json={"target_job_id": "thief"},
    )
    assert r.status_code == 200, r.json()

    db_helpers.set_job_level(ch["id"], 40)
    r = client.post(
        f"/api/characters/{ch['id']}/jobchange",
        headers=headers,
        json={"target_job_id": "assassin"},
    )
    assert r.status_code == 200, r.json()

    r = client.post(f"/api/characters/{ch['id']}/resetskills", headers=headers)
    assert r.status_code == 200, r.json()

    for skill_id in ("basic_attack_boost", "double_attack", "katar_mastery"):
        r = client.post(
            f"/api/characters/{ch['id']}/skills",
            headers=headers,
            json={"skill_id": skill_id, "level": 1},
        )
        assert r.status_code == 200, (skill_id, r.json())
        assert r.json()["learned_skills"][skill_id] == 1

    r = client.post(
        f"/api/characters/{ch['id']}/skills",
        headers=headers,
        json={"skill_id": "fire_bolt", "level": 1},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "非目前職業或前職技能"
