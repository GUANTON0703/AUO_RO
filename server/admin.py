import argparse

from server.config import get_settings
from server.db import connection


def _cmd_invite(count: int) -> None:
    from server.auth import invites

    connection.configure(get_settings().db_path)
    connection.init_db()
    for _ in range(count):
        print(invites.create_invite())


def _cmd_content_check() -> None:
    from server import content

    c = content.load_content()
    for name in ["monsters", "mvps", "maps", "jobs", "skills", "equipment", "cards", "items"]:
        print(f"{name}: {len(getattr(c, name))}")
    print("引用完整性：OK")


def _cmd_grant_gm(username: str) -> None:
    connection.configure(get_settings().db_path)
    connection.init_db()
    with connection.get_connection() as conn:
        cur = conn.execute("UPDATE accounts SET role = ? WHERE username = ?", ("GM遊戲管理者", username))
    if cur.rowcount != 1:
        raise SystemExit(f"找不到帳號：{username}")
    print(f"已授予 GM遊戲管理者：{username}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="server.admin", description="ROtxt 管理指令")
    sub = parser.add_subparsers(dest="command", required=True)

    p_invite = sub.add_parser("invite", help="產生邀請碼")
    p_invite.add_argument("--count", type=int, default=1)

    p_content = sub.add_parser("content", help="內容資料工具")
    p_content.add_argument("action", choices=["check"])

    p_gm = sub.add_parser("grant-gm", help="授予帳號 GM遊戲管理者角色")
    p_gm.add_argument("username")

    args = parser.parse_args()

    if args.command == "invite":
        _cmd_invite(args.count)
    elif args.command == "content" and args.action == "check":
        _cmd_content_check()
    elif args.command == "grant-gm":
        _cmd_grant_gm(args.username)


if __name__ == "__main__":
    main()
