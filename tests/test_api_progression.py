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
