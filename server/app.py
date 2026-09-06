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

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
