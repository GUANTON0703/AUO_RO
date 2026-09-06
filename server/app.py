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

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
