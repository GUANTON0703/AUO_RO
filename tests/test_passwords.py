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


def test_new_hash_uses_bcrypt_sha256():
    assert passwords.hash_password("x").startswith("$bcrypt-sha256$")


def test_verify_accepts_legacy_bcrypt_hash():
    from passlib.hash import bcrypt

    legacy = bcrypt.hash("old secret")
    assert passwords.verify_password("old secret", legacy) is True
    assert passwords.verify_password("wrong", legacy) is False


def test_long_and_multibyte_passwords_not_truncated():
    h = passwords.hash_password("a" * 72 + "TAIL")
    assert passwords.verify_password("a" * 72 + "DIFF", h) is False
    hz = passwords.hash_password("中文密碼" * 30)
    assert passwords.verify_password("中文密碼" * 30 + "x", hz) is False
