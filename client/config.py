import json
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".rotxt" / "session.json"


class SessionStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else _DEFAULT_PATH

    def load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None

    def save(self, **fields) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
