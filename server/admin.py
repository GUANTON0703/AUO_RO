import argparse

from server.config import get_settings
from server.db import connection


def _cmd_invite(count: int) -> None:
    from server.auth import invites

    for _ in range(count):
        print(invites.create_invite())


def main() -> None:
    parser = argparse.ArgumentParser(prog="server.admin", description="ROtxt 管理指令")
    sub = parser.add_subparsers(dest="command", required=True)

    p_invite = sub.add_parser("invite", help="產生邀請碼")
    p_invite.add_argument("--count", type=int, default=1)

    args = parser.parse_args()

    connection.configure(get_settings().db_path)
    connection.init_db()

    if args.command == "invite":
        _cmd_invite(args.count)


if __name__ == "__main__":
    main()
