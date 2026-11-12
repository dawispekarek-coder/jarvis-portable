"""Bridge daemon — the monitoring/reconciliation loop.

Runs the coordinator tick on an interval, snapshots state to
``dashboard_state.json`` + a self-refreshing HTML page, and keeps one
single-instance guard (Windows named mutex) so a restart can't run two
coordinators against the same queue.

Defaults to SAFE mode; AUTONOMOUS only when mode=autonomous AND
AUTONOMOUS_ENABLED.flag exists. The loop never removes holds, never
touches the legacy queue, and survives its own restart because all
state is on disk.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

from .bridge_store import atomic_write_json, utcnow

from .acp_client import DevinAcpClient
from .coordinator import Coordinator
from .dashboard import render_dashboard
from .github_probe import GithubProbe
from . import session_db

BRIDGE_ROOT = Path(__file__).resolve().parent
MUTEX_NAME = r"Local\RealJarvisDevinBridgeDaemon"


def _single_instance() -> bool:
    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != 183  # ALREADY_EXISTS


def make_coordinator(cfg: dict | None = None) -> Coordinator:
    cfg = cfg or {}
    gh = GithubProbe(token_file=Path(
        cfg.get("github_token_file",
                r"C:\Users\Dawis\ForeverRouteJarvis\github_token.dpapi")))
    return Coordinator(
        root=BRIDGE_ROOT,
        queue_root=Path(cfg.get("queue_root",
                                r"C:\Users\Dawis\ForeverRouteJarvis")),
        client_factory=lambda: DevinAcpClient(
            exe=cfg.get("devin_exe") or
            r"C:\Users\Dawis\AppData\Local\Programs\Devin\resources\app"
            r"\extensions\windsurf\devin\bin\devin.exe"),
        model=cfg.get("model", "swe-2-high"),
        mode=cfg.get("mode", "safe"),
        max_retries=int(cfg.get("max_retries", 2)),
        github=gh,
        protected_worktrees=cfg.get("protected_worktrees", []),
        authorized_worktrees=cfg.get("authorized_worktrees", []))


def load_config() -> dict:
    p = BRIDGE_ROOT / "bridge_config.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            pass
    return {}


def write_dashboard(coord: Coordinator, extra: dict | None = None) -> dict:
    st = coord.status()
    st["sessions_recent"] = session_db.list_sessions(limit=8)
    st["github"] = coord.github.status_summary() if coord.github else \
        {"available": False}
    st["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if extra:
        st.update(extra)
    from .bridge_store import atomic_write_json
    atomic_write_json(BRIDGE_ROOT / "dashboard_state.json", st)
    render_dashboard(st, BRIDGE_ROOT / "dashboard.html")
    return st


def run(interval_s: float = 60.0, once: bool = False) -> int:
    if not _single_instance():
        print("another bridge daemon is already running; exiting")
        return 0
    cfg = load_config()
    coord = make_coordinator(cfg)
    interval_s = float(cfg.get("poll_seconds", interval_s))
    print(f"DevinBridge daemon started | mode={coord.mode} | "
          f"model={coord.model} | poll={interval_s}s | root={BRIDGE_ROOT}")
    ticks = 0
    while True:
        ticks += 1
        # truthful heartbeat: the DAEMON writes it — a launcher saying
        # 'starting' after the process died is exactly the lie that
        # was reported. Absent file / stale ts = not running.
        try:
            atomic_write_json(
                BRIDGE_ROOT / "daemon_health.json",
                {"state": "running", "pid": os.getpid(),
                 "ticks": ticks, "mode": coord.mode,
                 "ts": utcnow()})
        except Exception:
            pass
        try:
            result = coord.tick()
            # CDP: collect evidence, generate deduped proposals, then a
            # controlled handoff that only fires inside a valid owner
            # program file — never outside its worktrees/kinds/budget.
            from . import cdp
            proposals = cdp.plan(coord)
            if proposals['created']:
                result['actions'].append('proposals awaiting approval: ' +
                                         str([p['proposal_id'] for p in proposals['created']]))
            if proposals.get('stopped'):
                result['actions'].append('planner STOP (stalled): ' +
                                         str(proposals['stopped']))
                cdp.escalate_stops(coord)
            # Closed loop: discover issues from fresh evidence,
            # synthesize tasks, hand off ONLY inside a program grant.
            from . import cdp_loop
            loop = cdp_loop.loop_tick(coord)
            if loop.get('created'):
                result['actions'].append(
                    f"cdp discovered+created: {loop['created']}")
            if loop.get('handoff', {}).get('handoff'):
                result['actions'].append(
                    f"cdp handoff dispatched {loop['handoff']['task_id']}")
            if loop.get('state') in ('STOP', 'WAITING_HUMAN'):
                result['actions'].append(
                    f"cdp {loop['state']}: {loop['reason'][:120]}")
            from . import recovery
            rec = recovery.tick(coord, notifier=None)
            if rec.get("acted"):
                result["actions"].extend(
                    f"recovery: {a}" for a in rec["acted"])
            from . import goals
            gt = goals.tick(coord)
            if gt.get("acted"):
                result["actions"].extend(
                    f"goal: {a}" for a in gt["acted"])
            from . import evidence_gap
            eg = evidence_gap.tick(coord)
            if eg.get("spawned"):
                result["actions"].extend(
                    f"gap: spawned {s}" for s in eg["spawned"])
            from . import learner
            try:
                ln = learner.tick(coord)
                if ln.get("new_lessons"):
                    result["actions"].append(
                        f"learned {ln['new_lessons']} lessons")
            except Exception as e:  # noqa: BLE001
                result["actions"].append(
                    f"learner: error {type(e).__name__}")
            from . import wow_qa_on_request
            try:
                qa = wow_qa_on_request.tick(coord)
                if qa.get('qa') not in ('idle', 'unauthorized'):
                    result["actions"].append(f"wow_qa: {qa}")
            except Exception as e:  # noqa: BLE001
                result["actions"].append(
                    f"wow_qa: error {type(e).__name__}")
            try:
                from . import supervisor_graph
                sv = supervisor_graph.supervisor_tick(coord)
                if sv.get("spawned"):
                    result["actions"].extend(
                        f"supervisor: spawned {s}"
                        for s in sv["spawned"])
            except Exception as e:  # noqa: BLE001 — never kill the tick
                result["actions"].append(
                    f"supervisor: error {type(e).__name__}")
            from .milestone_notifications import notify_scoped_milestones
            notify_scoped_milestones(coord)
            from .bridge_store import read_json as _rj
            write_dashboard(coord, {
                "last_tick": result,
                "supervisor": _rj(
                    BRIDGE_ROOT / "supervisor_state.json", {})})
            for a in result["actions"]:
                print(" ", a)
        except Exception as e:  # noqa: BLE001 — daemon must not die
            print(f"tick error: {e}")
        if once:
            break
        time.sleep(interval_s)
    return 0


if __name__ == "__main__":
    sys.exit(run(once="--once" in sys.argv))
