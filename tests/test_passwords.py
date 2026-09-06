from server.auth import passwords


def test_hash_then_verify_ok():
    h = passwords.hash_password("correct horse battery")
    assert h != "correct horse battery"
    assert passwords.verify_password("correct horse battery", h) is True


def test_verify_rejects_wrong():
    h = passwords.hash_password("right")
    assert passwords.verify_password("wrong", h) is False


def test_hashes_are_salted():
    assert passwords.hash_password("same") != passwords.hash_password("same")
