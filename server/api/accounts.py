from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth import invites, passwords, tokens
from server.auth.dependencies import CurrentAccount, TokenAndAccount
from server.config import get_settings
from server.db import connection
from server.repositories import accounts as accounts_repo
from shared.models import AccountPublic

router = APIRouter(prefix="/api", tags=["accounts"])


class RegisterRequest(BaseModel):
    invite_code: str
    username: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    account_id: int


class MeResponse(BaseModel):
    account_id: int
    username: str
    role: str
    is_gm: bool


class AnnouncementResponse(BaseModel):
    text: str
    updated_at: str | None = None


@router.post("/accounts", status_code=201, response_model=AccountPublic)
def register(body: RegisterRequest):
    # 便宜的預檢：擋掉明顯無效的邀請碼，避免對未驗證請求做昂貴的密碼雜湊。
    # 交易內還有一次權威檢查，並發安全性不靠這行。
    open_code = (get_settings().open_invite_code or "").strip()
    if body.invite_code != open_code and not invites.is_available(body.invite_code):
        raise HTTPException(status_code=400, detail="邀請碼無效或已被使用")
    try:
        account_id = accounts_repo.register_with_invite(
            body.username, passwords.hash_password(body.password), body.invite_code
        )
    except invites.InviteError:
        raise HTTPException(status_code=400, detail="邀請碼無效或已被使用")
    except accounts_repo.UsernameTakenError:
        raise HTTPException(status_code=409, detail="帳號名稱已被使用")
    return AccountPublic(id=account_id, username=body.username)


@router.post("/sessions", response_model=TokenResponse)
def login(body: LoginRequest):
    row = accounts_repo.get_account_by_username(body.username)
    if row is None or not passwords.verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    token = tokens.issue_token(row["id"], get_settings().token_ttl_hours)
    return TokenResponse(token=token, account_id=row["id"])


@router.get("/me", response_model=MeResponse)
def me(account_id: CurrentAccount):
    row = accounts_repo.get_account(account_id)
    if row is None:
        raise HTTPException(status_code=401, detail="帳號不存在")
    role = row["role"]
    return MeResponse(
        account_id=account_id,
        username=row["username"],
        role=role,
        is_gm=role == "GM遊戲管理者",
    )


@router.get("/announcement", response_model=AnnouncementResponse)
def get_announcement(_: CurrentAccount):
    with connection.get_connection() as conn:
        rows = dict(conn.execute(
            "SELECT key, value FROM server_settings "
            "WHERE key IN ('announcement', 'announcement_at')"
        ).fetchall())
    return AnnouncementResponse(text=rows.get("announcement", ""),
                                updated_at=rows.get("announcement_at"))


@router.delete("/sessions", status_code=204)
def logout(token_account: TokenAndAccount):
    token, _ = token_account
    tokens.revoke_token(token)
