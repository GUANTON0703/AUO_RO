from typing import Annotated

from fastapi import Depends, Header, HTTPException

from server.auth import tokens


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
