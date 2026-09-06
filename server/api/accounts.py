from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth import invites, passwords, tokens
from server.auth.dependencies import TokenAndAccount
from server.config import get_settings
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


@router.post("/accounts", status_code=201, response_model=AccountPublic)
def register(body: RegisterRequest):
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


@router.delete("/sessions", status_code=204)
def logout(token_account: TokenAndAccount):
    token, _ = token_account
    tokens.revoke_token(token)
