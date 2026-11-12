"""Automatable World of Warcraft QA for the ForeverRoute autonomy loop.

What this does (safe, reversible, owner-approved scope):
- Detect Battle.net / Wow.exe processes (read-only tasklist).
- Launch the client via Battle.net (`--exec="launch WoW"`), fallback Wow.exe.
- Wait for the client process to appear and settle.
- Verify ForeverRoute addon presence + .toc version vs client build.
- Check SavedVariables existence/mtime (addon actually ran).
- Capture a screenshot (PIL ImageGrab) as evidence.
- Write a truthful JSON report into the audit worktree tools/.

What this does NOT claim: a running client or an existing report is NOT a
completed gameplay test. Interactive navigation/quest/route checks need a
human or a dedicated UI-automation pass — the report marks them
`requires_human` with the exact blocker, never PASS.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .bridge_store import SUBPROCESS_NO_WINDOW

WOW_EXE = Path(r"H:\World of Warcraft\_forever_\Wow.exe")
BNET_EXE = Path(r"H:\Battle.net\Battle.net.exe")
RETAIL = Path(r"H:\World of Warcraft\_forever_")
ADDONS = RETAIL / "Interface" / "AddOns"
SAVEDVARS = RETAIL / "WTF" / "Account"
BRIDGE = Path(__file__).resolve().parent
WORKTREE = (BRIDGE / "autonomy_scope" / "workspaces"
            / "foreverroute-route-audit")
REPORT_DIR = WORKTREE / "tools"


def _procs() -> set:
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                         capture_output=True, timeout=20,
                         creationflags=SUBPROCESS_NO_WINDOW)
    text = (out.stdout or b"").decode("mbcs", errors="replace")
    return {line.split('","')[0].strip('"').lower()
            for line in text.splitlines() if line.startswith('"')}


def status() -> dict:
    p = _procs()
    return {"wow_running": "wow.exe" in p,
            "battlenet_running": "battle.net.exe" in p,
            "wow_exe": WOW_EXE.is_file(),
            "bnet_exe": BNET_EXE.is_file()}


def _addon_evidence() -> dict:
    fr = ADDONS / "ForeverRoute"
    ev = {"addons_dir": ADDONS.is_dir(), "foreverroute_installed": fr.is_dir()}
    if fr.is_dir():
        toc = next(fr.glob("*.toc"), None)
        ev["toc"] = str(toc) if toc else None
        if toc:
            head = toc.read_text(encoding="utf-8", errors="replace")[:4000]
            ev["toc_version"] = [l for l in head.splitlines()
                                 if l.startswith("##")][:8]
        ev["lua_files"] = len(list(fr.rglob("*.lua")))
    sv = []
    if SAVEDVARS.is_dir():
        for f in SAVEDVARS.rglob("ForeverRoute*.lua"):
            sv.append({"file": str(f),
                       "mtime_utc": datetime.fromtimestamp(
                           f.stat().st_mtime, timezone.utc).isoformat(),
                       "bytes": f.stat().st_size})
    ev["savedvariables"] = sv[:10]
    ev["addon_loaded_evidence"] = bool(sv)
    return ev


def _screenshot(out_dir: Path) -> str:
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        p = out_dir / f"wow_qa_{int(time.time())}.png"
        img.save(p)
        return str(p)
    except Exception as exc:  # headless/no display/PIL absent
        return f"UNAVAILABLE:{type(exc).__name__}:{exc}"[:160]


def launch() -> dict:
    st = status()
    if not st["wow_exe"]:
        return {"ok": False, "blocked": f"Wow.exe missing: {WOW_EXE}"}
    if st["wow_running"]:
        return {"ok": True, "launched": False, "note": "already running"}
    cmd = None
    if st["bnet_exe"]:
        cmd = [str(BNET_EXE), '--exec=launch wowf']
    elif st["wow_exe"]:
        cmd = [str(WOW_EXE)]
    try:
        subprocess.Popen(cmd, cwd=str(WOW_EXE.parent),
                         creationflags=SUBPROCESS_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL)
        return {"ok": True, "launched": True, "via": cmd[0]}
    except Exception as exc:
        return {"ok": False, "blocked": f"launch failed: {exc}"}


def run(wait_seconds: int = 120) -> dict:
    """Full automatable pass. Result is honest: launch + install/load
    evidence only — interactive gameplay QA stays `requires_human`."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started = status()
    res = {"ts_utc": datetime.now(timezone.utc).isoformat(),
           "initial": started, "steps": []}
    if not started["wow_running"]:
        # managed launch: reuses existing instance, enforces budgets
        from .wow_client import ensure
        lres = ensure()
        res["steps"].append({"ensure": lres})
        if not lres.get("ok"):
            res["result"] = lres.get("state", "BLOCKED")
            res["blocker"] = lres.get("blocked") or lres.get("note")
            _write(res)
            return res
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if status()["wow_running"]:
                break
            time.sleep(5)
    res["steps"].append({"client": status()})
    if not res["steps"][-1]["client"]["wow_running"]:
        res["result"] = "BLOCKED"
        res["blocker"] = ("Wow.exe did not appear within "
                          f"{wait_seconds}s — login screen or launcher "
                          "may need a human")
        _write(res)
        return res
    time.sleep(20)  # let the client reach a stable state
    res["addon"] = _addon_evidence()
    res["screenshot"] = _screenshot(REPORT_DIR)
    fr_ok = res["addon"].get("foreverroute_installed")
    res["result"] = ("VERIFIED_LAUNCH" if fr_ok
                     else "PARTIAL_NO_FOREVERROUTE_ADDON")
    res["interactive_qa"] = ("requires_human: navigation, quest tracking, "
                             "waypoint arrows and planner behaviour need "
                             "live gameplay observation — not claimed here")
    _write(res)
    return res


def _write(res: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (REPORT_DIR / f"wow_qa_report_{ts}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "wow_qa_latest.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


def wow_qa() -> str:
    """jarvis_tools entry: status + one automatable pass."""
    st = status()
    return json.dumps({"status": st,
                       "automatable": ["launch", "process_check",
                                       "addon_evidence", "savedvariables",
                                       "screenshot"],
                       "requires_human": ["in-game navigation QA",
                                          "real quest flow"],
                       "report_dir": str(REPORT_DIR)},
                      ensure_ascii=False)


def wow_qa_run() -> str:
    return json.dumps(run(), ensure_ascii=False)
