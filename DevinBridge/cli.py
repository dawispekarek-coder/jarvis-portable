"""Bridge CLI — human + Jarvis entry point.

    python -m DevinBridge.cli status
    python -m DevinBridge.cli queue
    python -m DevinBridge.cli add --id T900_DEMO --title "..." --prompt-file p.md --worktree DIR [--approve]
    python -m DevinBridge.cli approve T900_DEMO
    python -m DevinBridge.cli dispatch T900_DEMO [--force]
    python -m DevinBridge.cli verify T900_DEMO
    python -m DevinBridge.cli pause | resume
    python -m DevinBridge.cli mode safe|autonomous
    python -m DevinBridge.cli sessions
    python -m DevinBridge.cli dashboard
    python -m DevinBridge.cli daemon [--once]
    python -m DevinBridge.cli followup T900_DEMO --text "..."
    python -m DevinBridge.cli cancel T900_DEMO
    python -m DevinBridge.cli audit T148_P0_RELEASE_QUALITY_GATE
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .coordinator import Coordinator
from .daemon import make_coordinator, load_config, write_dashboard, BRIDGE_ROOT
from . import session_db


def _c() -> Coordinator:
    return make_coordinator(load_config())


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="devin_bridge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("queue")
    sub.add_parser("sessions")
    sub.add_parser("dashboard")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("approvals")
    sub.add_parser("notify-status")
    p = sub.add_parser("ntfy-confirm"); p.add_argument("dedup_key")
    p = sub.add_parser("notify-test")

    p = sub.add_parser("mode"); p.add_argument("mode",
                                             choices=["safe", "autonomous"])
    p = sub.add_parser("daemon"); p.add_argument("--once", action="store_true")
    p = sub.add_parser("server")
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("approve"); p.add_argument("id")
    p = sub.add_parser("reject"); p.add_argument("id")
    p = sub.add_parser("resume-task"); p.add_argument("id")
    p = sub.add_parser("dispatch"); p.add_argument("id")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("verify"); p.add_argument("id")
    p = sub.add_parser("cancel"); p.add_argument("id")
    p = sub.add_parser("task"); p.add_argument("id")
    p = sub.add_parser("audit"); p.add_argument("id")
    p = sub.add_parser("followup"); p.add_argument("id")
    p.add_argument("--text", required=True)
    p = sub.add_parser("add"); p.add_argument("--id", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--prompt", default="")
    p.add_argument("--prompt-file", default="")
    p.add_argument("--worktree", required=True)
    p.add_argument("--priority", type=int, default=50)
    p.add_argument("--depends-on", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--approve", action="store_true")
    p.add_argument("--human-gate", action="store_true")
    p.add_argument("--scope", default="", choices=["", "production", "test"])
    p.add_argument("--reason", default="")
    p.add_argument("--acceptance", default="",
                   help="JSON list of checks, e.g. "
                        '[{"type":"file_exists","path":"out.txt"}]')
    p = sub.add_parser("plan")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("promote"); p.add_argument("proposal_id")
    p = sub.add_parser("dismiss"); p.add_argument("proposal_id")
    p.add_argument("--note", default="")

    a = ap.parse_args(argv)
    c = _c()

    if a.cmd == "status":
        _print(c.status())
    elif a.cmd == "queue":
        _print(c.list_tasks())
    elif a.cmd == "task":
        _print(c.get_task(a.id))
    elif a.cmd == "sessions":
        _print(session_db.list_sessions(limit=20))
    elif a.cmd == "dashboard":
        st = write_dashboard(c)
        print(f"dashboard written: {BRIDGE_ROOT / 'dashboard.html'}")
        _print({"counts": st["counts"], "mode": st["mode"]})
    elif a.cmd == "pause":
        c.pause("cli")
        print("paused")
    elif a.cmd == "resume":
        c.resume()
        print("resumed")
    elif a.cmd == "mode":
        try:
            c.set_mode(a.mode)
        except PermissionError as e:
            print(str(e)); return 2
        print(f"mode={c.mode}")
    elif a.cmd == "approvals":
        from .approvals import ApprovalManager
        _print(ApprovalManager(c.root).pending())
    elif a.cmd == "approve":
        # Prefer deciding a pending approval REQUEST; fall back to the
        # legacy task-level approve+resume path.
        from .approvals import ApprovalManager
        mgr = ApprovalManager(c.root)
        if mgr.get(a.id):
            _print(mgr.decide(a.id, approved=True, decided_by="cli"))
        else:
            _print(c.approve(a.id))
    elif a.cmd == "reject":
        from .approvals import ApprovalManager
        mgr = ApprovalManager(c.root)
        if mgr.get(a.id):
            _print(mgr.decide(a.id, approved=False, decided_by="cli"))
        else:
            _print(c.deny(a.id, note="cli reject"))
    elif a.cmd == "resume-task":
        _print(c.resume_task(a.id))
    elif a.cmd == "notify-status":
        from .notify import Notifier
        _print(Notifier(c.root).states()[-15:])
    elif a.cmd == "ntfy-confirm":
        from .notify import Notifier
        _print(Notifier(c.root).mark_user_confirmed(a.dedup_key))
    elif a.cmd == "notify-test":
        from .notify import Notifier
        _print(Notifier(c.root).send(
            dedup_key=f"TEST|phone-test-{int(__import__('time').time())}",
            title="RealJarvis – Test upozornění",
            body="Test mobilních upozornění DevinBridge. "
                 "Potvrď prosím, zda zpráva dorazila.",
            priority="5", tags="test_tube,jarvis", urgent=True))
    elif a.cmd == "server":
        from .approval_server import serve
        return serve(a.bind, a.port) or 0
    elif a.cmd == "dispatch":
        _print(c.dispatch(a.id, force=a.force))
    elif a.cmd == "verify":
        _print(c.verify(a.id))
    elif a.cmd == "cancel":
        _print(c.cancel(a.id))
    elif a.cmd == "followup":
        t = c.get_task(a.id)
        if not t.get("session_id"):
            print("task has no session"); return 2
        try:
            cl = c._ensure_client()
            res = cl.session_prompt(t["session_id"], a.text)
            _print({"stop_reason": res.stop_reason,
                    "text": res.text[-2000:], "usage": res.usage})
        except Exception as e:
            print(f"followup failed: {e}"); return 1
    elif a.cmd == "add":
        prompt = a.prompt
        if a.prompt_file:
            prompt = Path(a.prompt_file).read_text(encoding="utf-8")
        if not prompt.strip():
            print("empty prompt"); return 2
        deps = [d.strip() for d in a.depends_on.split(",") if d.strip()]
        acc = []
        if a.acceptance:
            acc = json.loads(a.acceptance)
        _print(c.add_task(a.id, a.title or a.id, prompt, a.worktree,
                          priority=a.priority, depends_on=deps,
                          acceptance=acc, branch=a.branch,
                          human_gate=a.human_gate, approved=a.approve,
                          scope=a.scope, reason=a.reason))
    elif a.cmd == "plan":
        from . import planner
        res = planner.propose(c)
        _print({"new_proposals": res["created"],
                "open_total": res["open_total"],
                "proposals": [{"proposal_id": p["proposal_id"],
                               "title": p["title"],
                               "source": p["provenance"]["source"],
                               "reason": p["provenance"]["reason"]}
                              for p in planner.list_proposals(
                                  c, status="" if a.all else "OPEN")]})
    elif a.cmd == "promote":
        from . import planner
        _print(planner.promote(c, a.proposal_id))
    elif a.cmd == "dismiss":
        from . import planner
        _print(planner.dismiss(c, a.proposal_id, a.note))
    elif a.cmd == "daemon":
        from .daemon import run
        return run(once=a.once)
    elif a.cmd == "audit":
        # independent reconciliation evidence for a legacy-queue task
        qs = c.queue_root / "queue_state.json"
        from .bridge_store import read_json
        st = read_json(qs) or {}
        t = (st.get("tasks") or {}).get(a.id) or {}
        _print({"task_id": a.id, "queue_status": t.get("status"),
                "dispatchedHead": t.get("dispatchedHead"),
                "completedHead": t.get("completedHead"),
                "blockedObservedHead": t.get("blockedObservedHead"),
                "pendingDispatch": st.get("pendingDispatch"),
                "activeTaskId": st.get("activeTaskId"),
                "lastResult": st.get("lastResult")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
