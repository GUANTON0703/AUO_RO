from rich.console import Console
from rich.prompt import Prompt

from client.api import ApiClient, ApiError
from client.config import SessionStore

_console = Console()


def _login(api: ApiClient) -> str:
    while True:
        username = Prompt.ask("帳號")
        password = Prompt.ask("密碼", password=True)
        try:
            api.login(username, password)
            return username
        except ApiError as exc:
            _console.print(f"[red]登入失敗：{exc.detail}[/red]")


def _register(api: ApiClient) -> str:
    while True:
        code = Prompt.ask("邀請碼")
        username = Prompt.ask("帳號（3-20 字，英數底線）")
        password = Prompt.ask("密碼（至少 8 字）", password=True)
        try:
            api.register(code, username, password)
            api.login(username, password)
            return username
        except ApiError as exc:
            _console.print(f"[red]註冊失敗：{exc.detail}[/red]")


def ensure_logged_in(api: ApiClient, store: SessionStore, server_url: str) -> None:
    saved = store.load()
    if saved and saved.get("token") and saved.get("server_url") == server_url:
        api.token = saved["token"]
        try:
            api.list_characters()
            return
        except ApiError:
            api.token = None

    choice = Prompt.ask("[1] 登入　[2] 用邀請碼註冊", choices=["1", "2"], default="1")
    username = _login(api) if choice == "1" else _register(api)
    store.save(server_url=server_url, token=api.token, username=username)


def select_or_create_character(api: ApiClient) -> dict:
    chars = api.list_characters()
    if chars:
        return chars[0]
    name = Prompt.ask("建立角色，取個名字")
    return api.create_character(name)
