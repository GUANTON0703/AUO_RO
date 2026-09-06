from fastapi import APIRouter, HTTPException

from server.auth.dependencies import CurrentAccount
from server.repositories import leaderboard as leaderboard_repo

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
def get_leaderboard(account_id: CurrentAccount, by: str = "base_level"):
    try:
        return leaderboard_repo.top(by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
