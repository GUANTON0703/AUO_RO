import subprocess
import sys
import time

import httpx

from client.app import run

SERVER_URL = "http://127.0.0.1:8000"


def _wait_health(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{SERVER_URL}/health", timeout=1.0).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main() -> None:
    proc = subprocess.Popen([sys.executable, "-m", "server"])
    try:
        if not _wait_health():
            print("伺服器啟動逾時。")
            return
        run(SERVER_URL)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
