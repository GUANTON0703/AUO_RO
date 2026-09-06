from passlib.context import CryptContext

# 新密碼用 bcrypt_sha256（先 SHA256 再 bcrypt，繞開 bcrypt 原生 72-byte 截斷）。
# 保留 bcrypt 當 legacy scheme，舊 hash 仍驗得過，之後可自動升級。
_ctx = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated=["bcrypt"])


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
