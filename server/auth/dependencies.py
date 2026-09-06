from typing import Annotated

from fastapi import Depends, Header, HTTPException

from server.auth import tokens
from server.db import connection


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer token")
    return authorization.split(" ", 1)[1].strip()


def get_current_account(authorization: Annotated[str | None, Header()] = None) -> int:
    token = _extract_bearer(authorization)
    account_id = tokens.resolve_token(token)
    if account_id is None:
        raise HTTPException(status_code=401, detail="token 無效或已過期")
    return account_id


def get_token_and_account(
    authorization: Annotated[str | None, Header()] = None,
) -> tuple[str, int]:
    token = _extract_bearer(authorization)
    account_id = tokens.resolve_token(token)
    if account_id is None:
        raise HTTPException(status_code=401, detail="token 無效或已過期")
    return token, account_id


CurrentAccount = Annotated[int, Depends(get_current_account)]
TokenAndAccount = Annotated[tuple[str, int], Depends(get_token_and_account)]


def require_gm(account_id: CurrentAccount) -> int:
    with connection.get_connection() as conn:
        row = conn.execute("SELECT role FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None or row["role"] != "GM遊戲管理者":
        raise HTTPException(status_code=403, detail="需要 GM遊戲管理者 權限")
    return account_id


GMAccount = Annotated[int, Depends(require_gm)]
