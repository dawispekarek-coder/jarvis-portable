#!/usr/bin/env python3
"""init_project.py — onboard a NEW project for autonomous DevinBridge work.

Creates the program scope + goal authorization for an arbitrary repo,
points the bridge at it, enables autonomous mode. Re-run to switch
projects — previous state is archived, never deleted.

Usage:
    python init_project.py --repo "C:\\path\\to\\project" ^
        --goal "Ship a playable release" [--hours 24] [--paths *]

Defaults are deliberately conservative: no push/publish/install,
single worker, pacing + failure circuit breakers intact.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "DevinBridge"
SCOPE = BRIDGE / "autonomy_scope"
CONFIG = BRIDGE / "bridge_config.json"
COORD_STATE = BRIDGE / "coordinator_state.json"


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=4, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True,
                    help="absolute path to the project repo Jarvis should work on")
    ap.add_argument("--goal", required=True,
                    help="master goal text, e.g. 'release-ready v1.0'")
    ap.add_argument("--program-id", default=None,
                    help="default: derived from repo folder name")
    ap.add_argument("--hours", type=float, default=24.0,
                    help="authorization window in hours (default 24)")
    ap.add_argument("--paths", nargs="*", default=["*"],
                    help="allowed relative path prefixes inside the repo "
                         "(default '*' = whole repo; quote it)")
    ap.add_argument("--kinds", nargs="*",
                    default=["analyze", "docs", "test-add", "repair-small"],
                    help="allowed task kinds")
    ap.add_argument("--worktree", default=None,
                    help="worktree Jarvis edits (default: the repo itself)")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    if not repo.is_dir():
        print(f"ERROR: repo path does not exist: {repo}", file=sys.stderr)
        return 2
    worktree = Path(a.worktree).resolve() if a.worktree else repo
    if not worktree.is_dir():
        print(f"ERROR: worktree does not exist: {worktree}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    pid = a.program_id or (
        "PROJ_" + "".join(c if c.isalnum() else "_"
                          for c in repo.name.upper())[:24])
    expires = time.time() + a.hours * 3600

    program = {
        "program_id": pid,
        "ongoing": True,
        "owner_authorized": True,
        "owner_intent": a.goal,
        "worktrees": [str(worktree)],
        "kinds": a.kinds,
        "allowed_paths": a.paths,
        "max_dispatches_per_hour": 12,
        "max_failures_per_24h": 6,
        "max_parallel_workers": 1,
        "allow_publish": False,
        "allow_push": False,
        "allow_install": False,
        "sources": [],
        "prohibited": [
            "live-WoW", "SavedVariables", "remote network push",
            "release", "paid API enrollment",
        ],
        "attempts_per_task": 2,
        "max_tokens": 200000,
        "max_reported_tokens_per_24h": 1500000,
        "cached_read_weight": 0.5,
        "max_raw_reported_tokens_per_24h": 3000000,
    }
    _write_json(SCOPE / "CDP_PROGRAM.json", program)

    auth = {
        "program": pid,
        "granted_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "worktree": str(worktree),
        "allowed_task_ids": ["GOAL-*", "GEN-*", "RCV-*"],
        "kinds": a.kinds,
        "allowed_paths": a.paths,
        "attempts_per_task": 3,
        "max_tokens": 200000,
        "max_cost_usd": 5.0,
        "expires_epoch": expires,
        "expires_utc": datetime.fromtimestamp(
            expires, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "renewals": "re-run init_project.py to extend",
        "prohibited": [
            "push", "merge", "publish", "credential access",
            "destructive commands",
        ],
    }
    _write_json(SCOPE / f"{pid}_AUTHORIZATION.json", auth)

    goal_md = SCOPE / f"{pid}_MASTER_GOAL.md"
    goal_md.write_text(
        f"# Master goal\n\n{a.goal}\n\n"
        f"- Project repo: `{repo}`\n- Worktree: `{worktree}`\n"
        f"- Granted: {auth['granted_at_utc']} for {a.hours}h\n",
        encoding="utf-8")

    cfg = _load_json(CONFIG)
    cfg["authorized_worktrees"] = [str(worktree)]
    cfg["queue_root"] = str(SCOPE)
    _write_json(CONFIG, cfg)

    # Archive foreign-project queue state rather than mixing tasks.
    st = _load_json(COORD_STATE)
    tasks = (st.get("tasks") or {})
    foreign = any(str(t.get("worktree") or "") != str(worktree)
                  for t in tasks.values())
    if tasks and foreign:
        arch = BRIDGE / f"archive_state_{now.strftime('%Y%m%d_%H%M%S')}"
        arch.mkdir(exist_ok=True)
        for name in ("coordinator_state.json", "recovery_state.json",
                     "supervisor_state.json", "ai_planner_state.json",
                     "cdp_loop_state.json"):
            p = BRIDGE / name
            if p.is_file():
                shutil.move(str(p), str(arch / name))
        print(f"archived previous project state -> {arch}")

    st = _load_json(COORD_STATE)
    st.setdefault("tasks", {})
    st.setdefault("counts", {})
    st["mode"] = "autonomous"
    _write_json(COORD_STATE, st)
    (BRIDGE / "AUTONOMOUS_ENABLED.flag").write_text(
        f"autonomous enabled for {pid} at {auth['granted_at_utc']}\n",
        encoding="utf-8")

    print(f"OK: program {pid}")
    print(f"  worktree : {worktree}")
    print(f"  paths    : {a.paths}")
    print(f"  window   : {a.hours}h (until {auth['expires_utc']})")
    print("  mode     : autonomous + flag set")
    print("Start/restart the daemon; it will plan, dispatch and verify "
          "autonomously inside this scope.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
