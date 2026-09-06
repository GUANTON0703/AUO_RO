import subprocess
import sys

from server.db import connection


def test_invite_subcommand_creates_codes(tmp_path, monkeypatch):
    db = tmp_path / "admin.db"
    monkeypatch.setenv("ROTXT_DB_PATH", str(db))
    result = subprocess.run(
        [sys.executable, "-m", "server.admin", "invite", "--count", "3"],
        capture_output=True,
        text=True,
        cwd="H:/創業/ROtxt",
    )
    assert result.returncode == 0
    printed = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(printed) == 3

    connection.configure(str(db))
    with connection.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM invite_codes").fetchone()["c"]
    assert count == 3
