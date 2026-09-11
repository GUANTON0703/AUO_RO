from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.config import get_settings
from server.db import connection


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        connection._require_path()
    except RuntimeError:
        connection.configure(get_settings().db_path)
    connection.init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ROtxt", lifespan=_lifespan)

    from server.api.accounts import router as accounts_router

    app.include_router(accounts_router)

    from server.api.characters import router as characters_router

    app.include_router(characters_router)

    from server.api.progression import router as progression_router

    app.include_router(progression_router)

    from server.api.hunt import router as hunt_router

    app.include_router(hunt_router)

    from server.api.inventory import router as inventory_router

    app.include_router(inventory_router)

    from server.api.shop import router as shop_router

    app.include_router(shop_router)

    from server.api.storage import router as storage_router

    app.include_router(storage_router)

    from server.api.mvp import router as mvp_router

    app.include_router(mvp_router)

    from server.api.leaderboard import router as leaderboard_router

    app.include_router(leaderboard_router)

    from server.api.chat import router as chat_router

    app.include_router(chat_router)

    from server.api.trade import router as trade_router

    app.include_router(trade_router)

    from server.api.guild import router as guild_router

    app.include_router(guild_router)

    from server.api.content import router as content_router

    app.include_router(content_router)

    from server.api.admin import router as admin_router

    app.include_router(admin_router)

    from server.api.craft import router as craft_router

    app.include_router(craft_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """有 web/ 目錄就把網頁前端掛在根路徑（同源、免 CORS）。"""
    from pathlib import Path

    web_dir = Path(__file__).resolve().parent.parent / "web"
    if not (web_dir / "index.html").exists():
        return
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import Request

    @app.middleware("http")
    async def _no_stale_assets(request: Request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith("/api"):
            # 前端更新後使用者不用手動清快取；仍走 ETag/Last-Modified 條件請求
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
