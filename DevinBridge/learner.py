"""Self-improvement loop: distill lessons from finished work and feed
them back into planning.

Each daemon tick scans tasks for NEW terminal outcomes and derives a
structured lesson (what was attempted, outcome, rule to reuse). Lessons
are injected into ai_planner.build_context so every future proposal and
Devin prompt carries accumulated project knowledge — Jarvis plans with
its own experience, not from scratch every cycle.

Explicit lessons are also harvested: a worker report line
``LEARNED: <rule>`` is stored verbatim (highest-value signal — the
worker explains WHY in its own words).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .bridge_store import append_jsonl, atomic_write_json, \
    read_json, utcnow

LESSONS = "learned_lessons.jsonl"
STATE = "learner_state.json"
MAX_CONTEXT_LESSONS = 10

LEARNED_RE = re.compile(r"(?im)^\s*LEARNED\s*:\s*(.+)$")


def _files(root: Path):
    return root / LESSONS, root / STATE


def _derive(t: dict) -> dict | None:
    """One honest lesson from a terminal task. Never fabricates."""
    tid, kind = t.get("id"), t.get("kind") or t.get("goal_kind") or "?"
    title = (t.get("title") or "")[:90]
    status = t.get("status")
    if status == "COMPLETE":
        what = f"{kind} '{title}' succeeded"
        rule = "repeatable approach — reuse the same recipe"
    elif status in ("FAILED", "BLOCKED"):
        err = (t.get("last_error") or t.get("reason") or "")[:160]
        what = f"{kind} '{title}' {status.lower()}: {err}"
        rule = "avoid the failed approach or fix its precondition first"
    else:
        return None
    out = {"ts": utcnow(), "task_id": tid, "status": status,
           "kind": kind, "what": what, "rule": rule}
    # explicit worker lessons win over derived boilerplate
    learned = LEARNED_RE.findall(t.get("agent_text_tail") or "")
    if learned:
        out["explicit"] = [x.strip()[:200] for x in learned[:3]]
        out["rule"] = out["explicit"][0]
    return out


def tick(coord) -> dict:
    """Record lessons for tasks that reached a terminal state since the
    last tick. Idempotent via a processed-id cursor."""
    root = Path(coord.root)
    lpath, spath = _files(root)
    seen = set(read_json(spath, {}).get("done", []))
    new = []
    for t in coord.list_tasks():
        if t["id"] in seen:
            continue
        if t.get("status") not in ("COMPLETE", "FAILED", "BLOCKED"):
            continue
        les = _derive(t)
        seen.add(t["id"])
        if les:
            new.append(les)
            append_jsonl(lpath, les)
    atomic_write_json(spath, {"done": sorted(seen)[-500:]})
    return {"new_lessons": len(new)}


def lessons(root: Path, hints: list[str] | None = None,
            limit: int = MAX_CONTEXT_LESSONS) -> list[str]:
    """Recent + keyword-relevant lessons for the planner context."""
    lpath, _ = _files(Path(root))
    if not lpath.exists():
        return []
    rows = []
    for line in lpath.read_text(encoding="utf-8",
                                errors="replace").splitlines()[-200:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    keys = [h.lower() for h in (hints or []) if h]
    scored = sorted(
        rows, key=lambda r: (sum(k in json.dumps(r).lower()
                                 for k in keys), r.get("ts", "")),
        reverse=True)
    return [f"{r['status']} {r['task_id']}: {r['rule'][:140]}"
            for r in scored[:limit]]
