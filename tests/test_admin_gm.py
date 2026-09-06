import subprocess
import sys
import os

from server.db import connection
from server.repositories import accounts


def test_grant_gm_command_sets_named_role(tmp_path):
    db = tmp_path / "gm.db"
    connection.configure(str(db))
    connection.init_db()
    accounts.create_account("operator", "hash")
    result = subprocess.run(
        [sys.executable, "-m", "server.admin", "grant-gm", "operator"],
        capture_output=True, text=True, env={**os.environ, "ROTXT_DB_PATH": str(db)},
    )
    assert result.returncode == 0
    assert accounts.get_account_by_username("operator")["role"] == "GM遊戲管理者"
