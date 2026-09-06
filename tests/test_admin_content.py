import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_content_check_reports_counts():
    result = subprocess.run(
        [sys.executable, "-m", "server.admin", "content", "check"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0
    assert "monsters" in result.stdout
    assert "OK" in result.stdout or "通過" in result.stdout
