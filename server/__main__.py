import argparse

import uvicorn

from server.config import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="server", description="ROtxt FastAPI 伺服器")
    parser.add_argument("--host", default=settings.server_host, help="監聽位址")
    parser.add_argument("--port", type=int, default=settings.server_port, help="監聽 port")
    args = parser.parse_args()
    uvicorn.run(
        "server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
