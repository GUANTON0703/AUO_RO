from fastapi import FastAPI

from server.config import get_settings
from server.db import connection


def create_app() -> FastAPI:
    app = FastAPI(title="ROtxt")

    @app.on_event("startup")
    def _startup() -> None:
        try:
            connection._require_path()
        except RuntimeError:
            connection.configure(get_settings().db_path)
        connection.init_db()

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

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
