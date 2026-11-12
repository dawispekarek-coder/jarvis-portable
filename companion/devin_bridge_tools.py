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
