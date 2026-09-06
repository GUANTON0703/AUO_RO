import uvicorn

from server.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "server.app:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
