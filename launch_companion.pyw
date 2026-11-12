#!/usr/bin/env python3
"""launch_companion.pyw — portable companion launcher.

Starts the companion API (uvicorn on :7430) from the repo's own
companion/ dir, waits for /health, then opens the UI in the default
browser as an app-style window. Idempotent: if :7430 already serves
the companion, it just opens the window — no second instance.
"""
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPANION = ROOT / "companion"
PORT = 7430
URL = f"http://127.0.0.1:{PORT}"


def _health() -> dict | None:
    try:
        with urllib.request.urlopen(f"{URL}/health", timeout=2) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _pythonw() -> Path:
    venv = COMPANION / ".venv" / "Scripts" / "pythonw.exe"
    if venv.is_file():
        return venv
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.is_file() else exe


def main() -> None:
    h = _health()
    if not h:
        pyw = _pythonw()
        subprocess.Popen(
            [str(pyw), "-m", "uvicorn", "companion_api:app",
             "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=str(COMPANION),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,
                                  "CREATE_NO_WINDOW", 0))
        for _ in range(60):
            time.sleep(1)
            if _health():
                break
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
