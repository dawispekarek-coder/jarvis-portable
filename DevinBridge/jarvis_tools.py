"""Whitelisted tools the Devin chat brain may invoke via terminal.

The agent runs:
    python -m DevinBridge.jarvis_tools run <name> --json '{...}'

Every entry is read-only or coordinator-safe. Adding anything mutating
requires a human to edit this file AND pass the permission policy —
Jarvis-side tools (open apps, TTS, etc.) can be added later behind the
same gate. Output is plain text/JSON on stdout.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent


def _coordinator():
    from .daemon import load_config, make_coordinator
    return make_coordinator(load_config())


def get_time() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def get_date() -> str:
    return datetime.datetime.now().strftime("%A %Y-%m-%d")


def jarvis_status() -> str:
    c = _coordinator()
    st = c.status()
    return json.dumps({
        "mode": st.get("mode"), "paused": st.get("paused"),
        "model": st.get("model"), "counts": st.get("counts"),
        "holds": st.get("holds")}, ensure_ascii=False)


def devin_queue_status() -> str:
    c = _coordinator()
    rows = [{"id": t["id"], "status": t["status"], "title": t["title"]}
            for t in c.list_tasks()]
    return json.dumps(rows, ensure_ascii=False)


def foreverroute_goal() -> str:
    """Read-only owner master goal + verified current bridge goal states."""
    p = BRIDGE_ROOT / "autonomy_scope" / "FOREVERROUTE_MASTER_GOAL_20261111.md"
    if not p.is_file():
        return json.dumps({"available": False, "error": "master goal file missing"})
    try:
        from .bridge_store import read_json
        g = read_json(BRIDGE_ROOT / "goals.json", {})
        goals = [{"id": key, "state": val.get("state"),
                  "waiting_reason": val.get("waiting_reason")}
                 for key, val in g.get("goals", {}).items()
                 if isinstance(val, dict)]
        return json.dumps({"available": True, "goal_document": str(p),
                           "master_goal_excerpt": p.read_text(encoding="utf-8")[:3500],
                           "definition_of_done_excerpt": p.read_text(encoding="utf-8")[-2300:],
                           "full_goal_in_chat_home": "notes/FOREVERROUTE_MASTER_GOAL_20261111.md",
                           "excerpt_only": True,
                           "current_goals": goals}, ensure_ascii=False)
    except (OSError, ValueError, TypeError) as exc:
        return json.dumps({"available": False, "error": str(exc)[:200]})

def devin_live_status() -> str:
    """Read-only view of the two existing Devin Desktop sessions, via the
    DevinObserver snapshot. States are derived from activity timestamps —
    recent_visible_response is undated context, NEVER proof of current
    work."""
    from datetime import datetime, timezone
    path = BRIDGE_ROOT.parent / 'DevinObserver' / 'state.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        ts = datetime.fromisoformat(data['generated_at'])
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        sessions = {}
        for sid, item in data.get('sessions', {}).items():
            drv = item.get('derived') or {}
            sessions[sid] = {
                'found': item.get('found'),
                'state': drv.get('state', 'uncertain'),
                'activity_age_seconds': drv.get('activity_age_seconds'),
                'evidence': drv.get('evidence'),
                'identity_ok': drv.get('identity_ok'),
                'title': item.get('title'), 'cwd': item.get('cwd'),
                'agent_mode': item.get('agent_mode'),
                'recent_tools': item.get('recent_tools'),
                # Undated — context only, not proof of work now.
                'recent_visible_response':
                    (item.get('recent_visible_response') or '')[:400],
            }
        return json.dumps({'observer_age_seconds': round(age),
                           'fresh': 0 <= age < 210,
                           'stale_warning': age >= 210,
                           'sessions': sessions,
                           'foreverroute_git': data.get('foreverroute_git'),
                           'bridge': data.get('bridge')}, ensure_ascii=False)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return json.dumps({'available': False, 'error': str(exc)[:160]})

def _web_fetch(a: dict) -> str:
    from .web_research import web_fetch
    return web_fetch(a)


def _web_search(a: dict) -> str:
    from .web_research import web_search
    return web_search(a)


def _wow_manage() -> str:
    from .wow_client import wow_manage
    return wow_manage()


def _wow_qa_status() -> str:
    from .wow_qa import wow_qa
    return wow_qa()


def _wow_qa_run() -> str:
    from .wow_qa import wow_qa_run
    return wow_qa_run()


def devin_enqueue(a: dict) -> str:
    """Queue real work via the existing coordinator — no second queue.
    Chat-created tasks stay approved=False; approval is a separate,
    auditable decision (or delegated during the 24h trial)."""
    import uuid
    c = _coordinator()
    tid = f"CHAT-{uuid.uuid4().hex[:8].upper()}"
    res = c.add_task(
        tid, str(a.get("title") or "chat task")[:120],
        str(a.get("prompt") or ""),
        worktree=str(a.get("worktree") or
                     r"C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit"),
        priority=int(a.get("priority") or 50),
        acceptance=a.get("acceptance") or [],
        owner="jarvis", generated_by="jarvis-chat",
        reason=str(a.get("reason") or "operator chat request"),
        evidence_refs=a.get("evidence_refs") or [])
    return json.dumps({"task_id": tid, "ok": res.get("ok", True),
                       "note": "created approved=False — needs "
                               "devin_approve or delegation"})


def devin_approve(a: dict) -> str:
    """Approve a queued task. Allowed for chat (owner channel) always;
    logged via coordinator history. Trial delegation does NOT auto-
    approve chat tasks — an explicit call is the audit trail."""
    c = _coordinator()
    tid = str(a.get("task_id") or "")
    if not tid:
        return json.dumps({"ok": False, "error": "task_id required"})
    res = c.approve(tid, approved=bool(a.get("approved", True)))
    t = c.get_task(tid)
    return json.dumps({"ok": res.get("ok", True), "task_id": tid,
                       "status": t.get("status"),
                       "approved": t.get("approved")})


def pending_approvals() -> str:
    from .approvals import ApprovalManager
    c = _coordinator()
    pend = ApprovalManager(c.root).pending()
    return json.dumps(
        [{"request_id": r["request_id"], "summary": r["summary"],
          "risk": r["risk"], "task": r["task_id"]} for r in pend],
        ensure_ascii=False)


def devin_task(a: dict) -> str:
    """Show one task's full detail: prompt, acceptance, worktree, state,
    errors, evidence — so Jarvis can inspect work before driving it."""
    c = _coordinator()
    t = c.get_task(str(a.get("task_id") or ""))
    if not t:
        return json.dumps({"ok": False, "error": "unknown task"})
    keep = ("id", "title", "status", "approved", "human_gate", "scope",
            "kind", "priority", "attempts", "max_attempts", "worktree",
            "acceptance", "prompt", "last_error", "evidence_refs",
            "declared_followups", "recovery", "not_before", "created_at")
    return json.dumps({k: t.get(k) for k in keep}, ensure_ascii=False,
                      default=str)


def devin_next() -> str:
    """Which task the dispatcher would run next — with the reason if
    none is eligible. Read-only; never dispatches."""
    c = _coordinator()
    cand, why = c.next_eligible()
    return json.dumps({"next": (cand or {}).get("id"),
                       "title": (cand or {}).get("title"),
                       "reason": why}, ensure_ascii=False)


def devin_dispatch(a: dict) -> str:
    """Dispatch a READY+approved task to a SWE-2 worker. The coordinator
    enforces all gates itself (approval, scope, not_before, one worker
    per worktree) — this call cannot bypass them."""
    c = _coordinator()
    tid = str(a.get("task_id") or "")
    if not tid:
        return json.dumps({"ok": False, "error": "task_id required"})
    res = c.dispatch(tid)
    t = c.get_task(tid) or {}
    return json.dumps({"ok": bool(res.get("dispatched")), "task_id": tid,
                       "status": t.get("status"),
                       "worker_pid": t.get("worker_pid"),
                       "reason": res.get("reason")},
                      ensure_ascii=False)


def devin_verify(a: dict) -> str:
    """Run acceptance checks on a finished task — returns the machine
    verdict (VERIFIED/FAILED/UNKNOWN), never the agent's claim."""
    c = _coordinator()
    tid = str(a.get("task_id") or "")
    if not tid:
        return json.dumps({"ok": False, "error": "task_id required"})
    res = c.verify(tid)
    return json.dumps(res, ensure_ascii=False, default=str)


def approve_batch(a: dict) -> str:
    """Decide ALL pending requests of one task in a single audited
    batch — replaces the high-risk approval drip-feed. Scope is
    explicit: only that task's currently pending requests."""
    from .approvals import ApprovalManager
    c = _coordinator()
    tid = str(a.get("task_id") or "")
    if not tid:
        return json.dumps({"ok": False, "error": "task_id required"})
    res = ApprovalManager(c.root).decide_batch(
        tid, approved=bool(a.get("approved", True)),
        decided_by=str(a.get("decided_by") or "chat-owner"))
    return json.dumps(res)


TOOLS = {
    "get_time": {"fn": get_time, "desc": "current local time"},
    "get_date": {"fn": get_date, "desc": "current local date"},
    "jarvis_status": {"fn": jarvis_status,
                      "desc": "DevinBridge mode/pause/holds/task counts"},
    "foreverroute_goal": {"fn": foreverroute_goal, "desc": "Read owner ForeverRoute 1-60 goal, acceptance requirements and current goal states"},
    "devin_queue_status": {"fn": devin_queue_status,
                           "desc": "bridge task list with statuses"},
    "devin_enqueue": {"fn": devin_enqueue,
                      "desc": "queue real work via coordinator (title, "
                              "prompt, worktree, priority, acceptance); "
                              "creates approved=False"},
    "devin_approve": {"fn": devin_approve,
                      "desc": "approve a queued task (task_id, "
                              "approved) — auditable owner decision"},
    "devin_live_status": {"fn": devin_live_status, "desc": "read-only status of existing Devin Desktop sessions and Git"},
    "pending_approvals": {"fn": pending_approvals,
                          "desc": "actions awaiting human approval"},
    "approve_batch": {"fn": approve_batch,
                      "desc": "decide all pending approvals of one task "
                              "in a single audited batch (task_id, approved)"},
    "devin_task": {"fn": devin_task,
                   "desc": "full detail of one queue task "
                           "(prompt/acceptance/state/evidence)"},
    "devin_next": {"fn": devin_next,
                   "desc": "which task runs next + eligibility reason "
                           "(read-only)"},
    "devin_dispatch": {"fn": devin_dispatch,
                       "desc": "dispatch a READY+approved task to a "
                               "SWE-2 worker (all gates enforced)"},
    "devin_verify": {"fn": devin_verify,
                     "desc": "run acceptance checks → machine verdict "
                             "VERIFIED/FAILED/UNKNOWN"},
    "wow_qa": {"fn": _wow_qa_status,
               "desc": "WoW client/addon automatable QA status (read-only)"},
    "web_fetch": {"fn": _web_fetch,
                  "desc": "read allowlisted game-data URL (wowhead/wiki/github/ddg)"},
    "web_search": {"fn": _web_search,
                   "desc": "bounded DuckDuckGo search for missing quest/NPC data leads"},
    "wow_manage": {"fn": _wow_manage,
                   "desc": "WoW client manager: single-instance state, "
                           "reconnect/restart budget"},
    "wow_qa_run": {"fn": _wow_qa_run,
                   "desc": "run automatable WoW QA pass: launch client, "
                           "verify addon+SavedVariables, screenshot, report"},
}


def tools_doc() -> str:
    return "\n".join(f"- {name}: {t['desc']}" for name, t in TOOLS.items())


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="jarvis_tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("run")
    p.add_argument("name")
    p.add_argument("--json", default="{}")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        print(tools_doc())
        return 0
    t = TOOLS.get(a.name)
    if not t:
        print(f"unknown tool: {a.name}\navailable: {', '.join(TOOLS)}")
        return 2
    import inspect
    fn = t["fn"]
    if inspect.signature(fn).parameters:
        print(fn(json.loads(a.json)))
    else:
        print(fn())
    return 0


if __name__ == "__main__":
    sys.exit(main())
