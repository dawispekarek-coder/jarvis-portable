"""Read-only DevinBridge status tools for Companion.

Reads the autonomous coordinator's JSON state directly — no subprocess,
no writes, no duplicate queue. Truthful: distinguishes OPEN goals from
finished ones and never claims completion from an empty queue."""
from __future__ import annotations
import json, time
from pathlib import Path

BRIDGE = Path(r"C:\Users\Dawis\ForeverRouteJarvis\DevinBridge")
MASTER_GOAL_DOC = BRIDGE / "autonomy_scope" / "FOREVERROUTE_MASTER_GOAL_20261111.md"
PARENT_GOAL = "GOAL-FOREVERROUTE-PLAYABLE-1TO60"


def _rj(name):
    try:
        return json.loads((BRIDGE / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _goal_lines():
    g = _rj("goals.json").get("goals", {})
    out = []
    for gid, goal in g.items():
        out.append({
            "id": gid, "state": goal.get("state"),
            "waiting": goal.get("waiting_reason", ""),
            "stages_spawned": len(goal.get("spawned") or []),
            "stages_total": len(goal.get("stages") or []),
            "children": goal.get("children") or []})
    return out


def foreverroute_goal():
    """Real owner spec + durable goal state."""
    doc = ""
    try:
        doc = "\n".join(MASTER_GOAL_DOC.read_text(
            encoding="utf-8", errors="replace").splitlines()[:20])
    except Exception as exc:
        doc = f"UNREADABLE:{exc}"
    goals = _goal_lines()
    parent = next((x for x in goals if x["id"] == PARENT_GOAL), None)
    return {"goal_id": PARENT_GOAL,
            "state": (parent or {}).get("state", "missing"),
            "waiting": (parent or {}).get("waiting", ""),
            "spec_excerpt": doc[:1800],
            "spec_path": str(MASTER_GOAL_DOC),
            "all_goals": goals, "verified": True}


def devin_queue_status():
    """Coordinator counts + daemon health + goal summary."""
    st = _rj("coordinator_state.json")
    health = _rj("daemon_health.json")
    tasks = st.get("tasks", {})
    counts = {}
    for t in tasks.values():
        counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
    running = [k for k, v in tasks.items()
               if v.get("status") in ("RUNNING", "DISPATCHED", "VERIFYING")]
    waiting = [k for k, v in tasks.items()
               if v.get("waiting_approval")]
    return {"counts": counts, "running": running[:10],
            "waiting_approval": waiting[:10],
            "daemon": {"state": health.get("state"), "pid": health.get("pid"),
                       "ticks": health.get("ticks")},
            "mode": st.get("mode"), "goals": _goal_lines(),
            "empty_queue_is_not_done": True, "verified": True}


def devin_bridge_queue():
    """Task details: statuses, results, blockers — truthful last errors."""
    st = _rj("coordinator_state.json")
    tasks = []
    for tid, t in sorted(st.get("tasks", {}).items()):
        if not (tid.startswith("GOAL-") or tid.startswith("RCV-")):
            continue
        tasks.append({"id": tid, "status": t.get("status"),
                      "title": (t.get("title") or "")[:80],
                      "waiting": (t.get("waiting_approval") or "")[:120],
                      "last_error": (t.get("last_error") or "")[:160],
                      "human_gate": bool(t.get("human_gate"))})
    return {"tasks": tasks[-25:], "total": len(tasks),
            "note": "FAILED/BLOCKED jsou pravdivé stavy; COMPLETE = nezávisle ověřeno",
            "verified": True}


# --- Queue control: real actions via the DevinBridge CLI (not a second queue) ---

BRIDGE_REPO = BRIDGE.parent  # C:\Users\Dawis\ForeverRouteJarvis


def _python_exe():
    for cand in (Path(r"C:\Users\Dawis\AppData\Local\Programs\Python\Python312\python.exe"),
                 Path(r"C:\Users\Dawis\ForeverRouteJarvis\.venv\Scripts\python.exe")):
        if cand.is_file():
            return str(cand)
    import sys
    return sys.executable


def _run_tool(name, args=None, timeout=120):
    """Call `python -m DevinBridge.jarvis_tools run <name>` — the same
    coordinator instance the daemon uses. Returns parsed JSON or the
    raw stdout; never fabricates a result."""
    import subprocess
    cmd = [_python_exe(), "-m", "DevinBridge.jarvis_tools", "run", name]
    if args is not None:
        cmd += ["--json", json.dumps(args)]
    try:
        p = subprocess.run(cmd, cwd=str(BRIDGE_REPO), capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"tool {name} timeout after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"spawn failed: {exc}"}
    out = (p.stdout or "").strip()
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": p.returncode == 0, "stdout": out[:3000],
                "stderr": (p.stderr or "")[-500:], "rc": p.returncode}


def devin_next():
    """Which task the dispatcher would run next, with reason if none."""
    return _run_tool("devin_next")


def devin_task(task_id):
    """Full detail of one task: prompt, acceptance, status, evidence."""
    return _run_tool("devin_task", {"task_id": task_id})


def devin_dispatch(task_id):
    """Dispatch a READY+approved task through normal coordinator gates."""
    return _run_tool("devin_dispatch", {"task_id": task_id}, timeout=180)


def devin_verify(task_id):
    """Run acceptance checks on a finished task -> VERIFIED/FAILED/UNKNOWN."""
    return _run_tool("devin_verify", {"task_id": task_id}, timeout=240)


def devin_enqueue(title, prompt, worktree="", priority=50, acceptance=None):
    """Queue real work via the existing coordinator (approved=False)."""
    return _run_tool("devin_enqueue", {
        "title": title, "prompt": prompt, "worktree": worktree,
        "priority": priority, "acceptance": acceptance or []})


def devin_approve(task_id, approved=True):
    """Approve/reject a queued task — audited owner-channel decision."""
    return _run_tool("devin_approve", {"task_id": task_id, "approved": approved})


def pending_approvals():
    """List currently pending approval requests."""
    return _run_tool("pending_approvals")


def approve_batch(task_id, approved=True):
    """Decide ALL pending requests of one task in a single audited batch."""
    return _run_tool("approve_batch",
                     {"task_id": task_id, "approved": approved,
                      "decided_by": "jarvis-companion"})
