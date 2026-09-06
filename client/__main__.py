import argparse

from client.app import run
from client.config import SessionStore
from client.terminal import prepare_windows_console


def main() -> None:
    prepare_windows_console()
    parser = argparse.ArgumentParser(prog="client", description="ROtxt 終端機客戶端")
    parser.add_argument("--server", default=None, help="伺服器網址")
    args = parser.parse_args()

    server_url = args.server
    if not server_url:
        saved = SessionStore().load() or {}
        server_url = saved.get("server_url") or "http://127.0.0.1:8000"
    run(server_url)


if __name__ == "__main__":
    main()
