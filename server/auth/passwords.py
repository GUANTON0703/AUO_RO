from passlib.context import CryptContext

# bcrypt_sha256：先 SHA256 再 bcrypt，繞開 bcrypt 原生 72-byte 截斷，
# 長密碼與多位元組密碼不會被靜默吃掉。
_ctx = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
