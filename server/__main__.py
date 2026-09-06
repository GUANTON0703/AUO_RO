import uvicorn

from server.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "server.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
