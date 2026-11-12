"""DevinBridge daemon watchdog — keeps the autonomous loop alive.

Runs detached (pythonw). Every 60s:
  * no `python -m DevinBridge.daemon` process -> relaunch
  * supervisor_state.json stale > 10 min while process exists ->
    kill + relaunch (hung daemon)

Not a scheduler and not a second queue — it only respawns the existing
daemon entry point. Logs to daemon_watchdog.log.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "supervisor_state.json"
LOG = ROOT / "daemon_watchdog.log"
PY = sys.executable.replace("pythonw", "python")
STALE_S = 600
POLL_S = 60

FIND = ("Get-CimInstance Win32_Process -Filter \"CommandLine like "
        "'%DevinBridge.daemon%'\" | Select -Expand ProcessId")


def _pids() -> list[int]:
    r = subprocess.run(["powershell", "-c", FIND],
                       capture_output=True, text=True, timeout=30,
                       creationflags=0x08000000)  # CREATE_NO_WINDOW
    out = []
    for tok in r.stdout.split():
        try:
            pid = int(tok)
        except ValueError:
            continue
        if pid != 0:
            out.append(pid)
    return out


def _log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
                f"{msg}\n")


def _spawn() -> None:
    subprocess.Popen(
        [PY, "-u", "-m", "DevinBridge.daemon"],
        cwd=str(ROOT.parent), stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        creationflags=0x00000008 | 0x08000000)  # DETACHED + NO_WINDOW
    _log("daemon respawned")


def main() -> None:
    _log("watchdog start")
    while True:
        try:
            pids = _pids()
            if not pids:
                _spawn()
            elif time.time() - STATE.stat().st_mtime > STALE_S:
                for pid in pids:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                   capture_output=True, timeout=15,
                                   creationflags=0x08000000)
                _log(f"stale heartbeat >{STALE_S}s — killed {pids}")
                time.sleep(5)
                _spawn()
        except Exception as e:  # noqa: BLE001 — watchdog must never die
            _log(f"watchdog error {type(e).__name__}: {e}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
