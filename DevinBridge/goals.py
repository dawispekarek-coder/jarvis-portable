"""Durable project GOALS — the autonomy root cause fix.

A goal is an OUTCOME CONTRACT, not a queue entry. It stays OPEN until
its contract checks independently prove completion — no matter how many
child tasks end COMPLETE/VERIFIED_RECOVERED. After every tick the goal
re-evaluates evidence and, when gaps remain and nothing is running,
spawns the next bounded stage task with a stable fingerprint ID.

Safety: stages inside a live owner grant dispatch automatically; stages
outside any grant are queued as real tasks with approved=False +
waiting_approval=True and the owner is notified ONCE via ntfy — never
silently idle, never self-approved.
"""
from __future__ import annotations

import fnmatch
import json
import time
from pathlib import Path

from .bridge_store import (atomic_write_json, file_lock, read_json,
                           utcnow)

GOALS_FILE = "goals.json"


def _load(root: Path) -> dict:
    d = read_json(root / GOALS_FILE, {})
    d.setdefault("goals", {})
    return d


def _save(root: Path, d: dict) -> None:
    atomic_write_json(root / GOALS_FILE, d)


def add_goal(root: Path, goal_id: str, title: str, worktree: str,
             contract: list[dict], stages: list[dict],
             provenance: str, evidence_request: str = "",
             children: list = None) -> dict:
    """contract: acceptance-style checks evaluated against the worktree
    (file_exists/file_contains). stages: ordered dicts
    {title, prompt, acceptance, kind, human_gate?, needs_evidence?}."""
    d = _load(root)
    if goal_id in d["goals"]:
        return {"added": False, "goal": d["goals"][goal_id]}
    d["goals"][goal_id] = {
        "id": goal_id, "title": title, "worktree": worktree,
        "state": "OPEN", "contract": contract, "stages": stages,
        "provenance": provenance, "evidence_request": evidence_request,
        "children": list(children or []),
        "created_at": utcnow(), "spawned": [], "notified": False,
        "waiting_reason": "", "completed_at": ""}
    _save(root, d)
    return {"added": True, "goal": d["goals"][goal_id]}


def _contract_passes(g: dict) -> tuple[bool, list]:
    results = []
    wt = Path(g["worktree"])
    for chk in g.get("contract") or []:
        p = chk.get("path", "")
        fp = (wt / p).resolve()
        ok = False
        try:
            fp.relative_to(wt.resolve())
            if chk["type"] == "file_exists":
                ok = fp.exists()
            elif chk["type"] == "file_contains" and fp.exists():
                ok = chk.get("pattern", "") in fp.read_text(
                    encoding="utf-8", errors="replace")
        except Exception:
            ok = False
        results.append({"check": f"{chk['type']} {p}", "ok": ok})
    return bool(results) and all(r["ok"] for r in results), results


def _grant(coord, worktree: str, task_id: str, kind: str) -> tuple:
    """Live owner grant allowing THIS task id + kind — fnmatch patterns
    allowed (e.g. GOAL-FR-WP-*). Same fields as recovery.check_grant."""
    scope = coord.root / "autonomy_scope"
    if not scope.is_dir():
        return False, "no authorization dir"
    wt = str(Path(worktree).resolve()).casefold()
    for f in scope.glob("*AUTHORIZATION*.json"):
        a = read_json(f, {})
        if not a or str(Path(a.get("worktree", "")).resolve()
                         ).casefold() != wt:
            continue
        if float(a.get("expires_epoch") or 0) <= time.time():
            return False, "authorization expired"
        if not any(fnmatch.fnmatch(task_id, pat)
                   for pat in (a.get("allowed_task_ids") or [])):
            return False, "task id not in allowed_task_ids"
        if kind not in set(a.get("kinds") or a.get("allowed_kinds") or []):
            return False, f"kind {kind} not granted"
        if not int(a.get("attempts_per_task") or 0) >= 1:
            return False, "no attempts_per_task limit"
        return True, a
    return False, "no grant covers this worktree"


def _stage_state(g: dict, coord, i: int) -> tuple:
    """(status, attempt_task_ids) for stage i — retry attempts share the
    stage prefix S{i+1:02d} with an -R<n> suffix."""
    base = f"{g['id']}-S{i + 1:02d}"
    attempts = [s for s in g["spawned"]
                if s == base or s.startswith(base + "-R")]
    if not attempts:
        return "not_spawned", attempts
    for s in attempts:
        if (coord.get_task(s) or {}).get("status") in (
                "COMPLETE", "VERIFIED_RECOVERED"):
            return "complete", attempts
    return (coord.get_task(attempts[-1]) or {}).get("status",
                                                   "missing"), attempts


_LIVE = ("PENDING", "READY", "DISPATCHED", "RUNNING", "VERIFYING",
         "NEEDS_REVIEW")
MAX_STAGE_ATTEMPTS = 3  # owner-approved ceiling, 2026-11-11


def tick(coord, notifier=None) -> dict:
    """Re-evaluate every OPEN goal; spawn/dispatch or queue-for-approval
    the next stage. Called from the daemon tick after recovery.tick."""
    root = coord.root
    d = _load(root)
    acted = []
    for g in d["goals"].values():
        if g["state"] != "OPEN":
            continue
        done, results = _contract_passes(g)
        kids = g.get("children") or []
        if kids:
            # parent goal — OPEN until children done AND contract (which
            # includes human attestation) independently passes
            kstat = {k: (d["goals"].get(k) or {}).get("state", "missing")
                     for k in kids}
            if done and all(v == "DONE" for v in kstat.values()):
                g["state"] = "DONE"
                g["completed_at"] = utcnow()
                coord._event("goal_complete", goal=g["id"],
                             contract=results)
                acted.append(f"goal {g['id']} DONE")
            else:
                g["waiting_reason"] = " | ".join(
                    f"{k}={v}" for k, v in kstat.items()) + (
                    " · awaiting human attestation" if all(
                        v == "DONE" for v in kstat.values()) else "")
            continue
        if done:
            g["state"] = "DONE"
            g["completed_at"] = utcnow()
            coord._event("goal_complete", goal=g["id"],
                         contract=results)
            acted.append(f"goal {g['id']} DONE")
            continue
        # re-evaluate WAITING_APPROVAL stages under the CURRENT grant —
        # a newly issued owner authorization activates them in place
        for s in g["spawned"]:
            t = coord.get_task(s) or {}
            if (t.get("status") == "PENDING" and
                    t.get("waiting_approval") and
                    not t.get("human_gate")):
                gok, ga = _grant(coord, g["worktree"], s,
                                 t.get("goal_kind", "analyze"))
                if gok:
                    def _ap(x, ga=ga):
                        x["approved"] = True
                        x["waiting_approval"] = ""
                        x["max_tokens"] = int(
                            ga.get("max_tokens") or 0)
                    coord._mutate(s, _ap)
                    disp = coord.dispatch(s)
                    if disp.get("dispatched"):
                        g["waiting_reason"] = ""
                    else:
                        g["waiting_reason"] = (
                            f"{s}: approved, waiting for worktree "
                            f"({disp.get('reason', 'held')})")
                    acted.append(f"goal {g['id']} approved+dispatched "
                                 f"{s} ({disp.get('dispatched')})")
        # token guard — a stage that blows the grant's per-task cap
        # halts the chain fail-closed (owner decides, never renews)
        over = False
        for s in g["spawned"]:
            rf = read_json(coord.root / "runs" / f"{s}.result.json", {})
            used = int((rf.get("usage") or {}).get("totalTokens") or 0)
            lim = int((coord.get_task(s) or {}).get("max_tokens") or 0)
            if lim and used > lim:
                g["waiting_reason"] = (
                    f"stage {s} exceeded token cap {used}>{lim} — "
                    "halting, owner decision required")
                over = True
        if over:
            continue
        # find the FIRST stage not yet proven — live stages pause the
        # goal; FAILED stages retry within the grant's attempt budget
        idx = att_n = None
        prompt_extra = ""
        for i in range(len(g["stages"])):
            st, att = _stage_state(g, coord, i)
            if st == "complete":
                continue
            if st in _LIVE:
                idx = None
                break  # stage i is being worked on
            if st in ("FAILED", "BLOCKED"):
                gok_r, ga_r = _grant(
                    coord, g["worktree"],
                    f"{g['id']}-S{i + 1:02d}-R{len(att) + 1}",
                    g["stages"][i].get("kind", "analyze"))
                cap = min(int((ga_r or {}).get("attempts_per_task")
                              or (1 if gok_r else 0)),
                          MAX_STAGE_ATTEMPTS)
                if len(att) < cap:
                    idx, att_n = i, len(att)
                    last = coord.get_task(att[-1]) or {}
                    fails = [c["check"] for c in (last.get(
                        "evidence") or {}).get("checks", [])
                             if not c.get("ok")]
                    prompt_extra = (
                        f"\nPREVIOUS ATTEMPT {att[-1]} FAILED "
                        f"({last.get('last_error', '')[:200]}). "
                        f"Failed checks: {fails}. Reconcile REAL "
                        "artifacts already produced in the repo (see "
                        "tools/*2026*.json and recent commits) — produce "
                        "the exact acceptance artifacts; never fabricate "
                        "data or rename junk to pass.")
                    break
                g["waiting_reason"] = (
                    f"stage S{i + 1:02d} failed {len(att)}x — owner gate")
                idx = None
                break
            idx, att_n = i, 0
            break
        if idx is None:
            if all(_stage_state(g, coord, i)[0] == "complete"
                   for i in range(len(g["stages"]))):
                if not g.get("notified"):
                    g["waiting_reason"] = (
                        "all stages spawned but contract still unmet — "
                        "needs new evidence/stages")
                    if notifier:
                        notifier.task_failed(
                            f"Goal stalled: {g['title'][:50]}",
                            g["waiting_reason"],
                            g.get("evidence_request", ""))
                    g["notified"] = True
            continue
        st_def = g["stages"][idx]
        tid = (f"{g['id']}-S{idx + 1:02d}" if not att_n
               else f"{g['id']}-S{idx + 1:02d}-R{att_n + 1}")
        kind = st_def.get("kind", "analyze")
        human = bool(st_def.get("human_gate"))
        gok, ga = _grant(coord, g["worktree"], tid, kind)
        greason = ga if not gok else ""
        approved = gok and not human
        res = coord.add_task(
            tid, st_def["title"], st_def["prompt"] + prompt_extra,
            g["worktree"],
            priority=st_def.get("priority", 40),
            acceptance=st_def.get("acceptance") or [],
            approved=approved, scope="production",
            owner="goal", generated_by="goal",
            human_gate=human,
            reason=f"goal {g['id']} stage {idx + 1}: {st_def['title']}",
            evidence_refs=[f"goal:{g['id']}", g.get("provenance", "")],
            max_attempts=1)
        if not res.get("added"):
            g["waiting_reason"] = res.get("reason", "spawn failed")
            continue
        g["spawned"].append(tid)
        coord._mutate(tid, lambda x: x.__setitem__("goal_kind", kind))
        if gok and isinstance(ga, dict):
            coord._mutate(tid, lambda x: x.__setitem__(
                "max_tokens", int(ga.get("max_tokens") or 0)))
        if human:
            coord._mutate(tid, lambda x: x.__setitem__(
                "waiting_approval", st_def.get("needs_evidence") or
                g.get("evidence_request") or "human action required"))
            g["waiting_reason"] = f"{tid}: human gate"
            acted.append(f"goal {g['id']} stage {tid} waits for human")
        elif not approved:
            coord._mutate(tid, lambda x: x.__setitem__(
                "waiting_approval", f"no grant: {greason}"))
            g["waiting_reason"] = f"{tid}: {greason}"
            acted.append(f"goal {g['id']} stage {tid} queued "
                         f"WAITING_APPROVAL ({greason})")
            if notifier and not g.get("notified"):
                notifier.task_failed(
                    f"Approval needed: {st_def['title'][:50]}",
                    f"{tid} in {g['worktree']}",
                    "open dashboard to approve")
                g["notified"] = True
        else:
            disp = coord.dispatch(tid)
            g["waiting_reason"] = (
                "" if disp.get("dispatched")
                else f"{tid}: approved, {disp.get('reason','held')}")
            acted.append(f"goal {g['id']} dispatched {tid} "
                         f"({disp.get('dispatched')})")
        coord._event("goal_stage_spawned", goal=g["id"], task=tid,
                     approved=approved, stage_kind=kind)
    _save(root, d)
    return {"acted": acted}


def summary(root: Path) -> list[dict]:
    """Truthful status for chat/dashboard — never claims done."""
    d = _load(root)
    out = []
    for g in d["goals"].values():
        done, results = _contract_passes(g)
        out.append({"id": g["id"], "title": g["title"],
                    "state": g["state"], "contract_ok": done,
                    "spawned": g["spawned"],
                    "next_stage": len(g["spawned"]) + 1,
                    "total_stages": len(g["stages"]),
                    "waiting": g.get("waiting_reason", ""),
                    "checks": results})
    return out
