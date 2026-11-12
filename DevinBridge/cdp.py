"""Continuous Development Planner (CDP).

P0 collect(): durable per-task evidence — acceptance results, git diff
stat, produced docs, errors, staleness. Verified == acceptance checks
passed; agent text is "asserted" evidence only; nothing here can mark
work as WoW-client-tested (that level is 'human_tested' and is never
set by the bridge).

P1 plan(): fingerprinted, deduped, budgeted proposals derived from
collected evidence + declared follow-ups + unresolved failure records.
Anti-loop: a fingerprint that fails >= STALL_CAP times goes to STOP —
escalated to the human instead of silently re-proposed.

P2 handoff_tick(): controlled autonomous handoff — promotes OPEN
proposals into dispatched tasks ONLY inside a valid program
authorization file. Absent/expired/ambiguous file → fail closed, no
dispatch, optional ntfy. A proposal can never widen scope: promotion
inherits exactly the program's allowed worktrees/kinds.

P3 failure memory lives on the proposal records themselves
(fingerprint, attempts, outcomes, reasons) + escalation via notifier.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

from .bridge_store import (SUBPROCESS_NO_WINDOW, atomic_write_json,
                           prompt_sha, read_json,
                           utcnow)
from . import planner as base_planner

EVIDENCE_DIR = "evidence"
STALL_CAP = 2            # same fingerprint failed twice -> STOP
PROGRAM_FILE = "autonomy_scope/CDP_PROGRAM.json"
BACKLOG_FILE = "cdp_backlog.json"

# Proposal kinds a program may authorize; anything else waits for the
# phone. Never includes publish/push/destructive kinds.
SAFE_KINDS = {"analyze", "repair-small", "test-add", "docs"}
ALWAYS_HUMAN = {"publish", "push", "merge", "destructive", "install",
                "credential", "scope-expand", "wow-client", "release"}


def _fp(kind: str, source: str, signature: str) -> str:
    return hashlib.sha256(
        f"{kind}|{source}|{signature}".encode()).hexdigest()[:20]


# ------------------------------------------------------------- P0 evidence
def collect(coord, task_id: str) -> dict:
    """Snapshot one task's evidence to evidence/<id>.json (idempotent)."""
    t = coord.get_task(task_id)
    if not t:
        return {"ok": False, "error": "unknown task"}
    wt = Path(t["worktree"])
    ev = {"task_id": task_id, "title": t.get("title"),
          "status": t.get("status"), "collected_at": utcnow(),
          "verified": None,          # True only if acceptance passed
          "checks": (t.get("evidence") or {}).get("checks", []),
          "asserted_tail": (t.get("agent_text_tail") or "")[-600:],
          "base_head": t.get("base_head"), "result_head": t.get("result_head"),
          "attempts": t.get("attempts", 0),
          "last_error": t.get("last_error", ""),
          "produced_files": [], "diff_stat": {},
          "confidence": "verified" if t.get("status") == "COMPLETE"
                        else "incomplete",
          "human_tested": False}     # bridge can never set this
    # git diff evidence (read-only)
    try:
        if wt.is_dir() and t.get("base_head") and t.get("result_head"):
            out = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(wt),
                 "diff", "--stat", "--name-only",
                 f"{t['base_head']}..{t['result_head']}"],
                capture_output=True, text=True, timeout=15,
                creationflags=SUBPROCESS_NO_WINDOW)
            if out.returncode == 0:
                files = [l for l in out.stdout.splitlines() if l.strip()]
                ev["produced_files"] = files[:50]
                ev["diff_stat"] = {"files_changed": len(files)}
    except Exception:
        pass
    # uncommitted files the agent may have produced
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(wt),
             "status", "--porcelain=v1", "-uall"],
            capture_output=True, text=True, timeout=15,
            creationflags=SUBPROCESS_NO_WINDOW)
        if out.returncode == 0:
            dirty = [l[3:] for l in out.stdout.splitlines() if l.strip()]
            for f in dirty:
                if f not in ev["produced_files"]:
                    ev["produced_files"].append(f)
    except Exception:
        pass
    if t.get("status") == "COMPLETE" and ev["checks"]:
        ev["verified"] = all(c.get("ok") for c in ev["checks"])
    elif t.get("status") == "COMPLETE":
        ev["verified"] = True   # no declared checks; head-move counted
    else:
        ev["verified"] = False
    path = coord.root / EVIDENCE_DIR / f"{task_id}.json"
    atomic_write_json(path, ev)
    return {"ok": True, "evidence": ev, "path": str(path)}


def collect_all_terminal(coord) -> int:
    n = 0
    for t in coord.list_tasks():
        if t["status"] in ("COMPLETE", "FAILED", "BLOCKED") and \
                t.get("scope") == "production":
            if collect(coord, t["id"]).get("ok"):
                n += 1
    return n


def load_evidence(coord, task_id: str) -> dict:
    return read_json(coord.root / EVIDENCE_DIR / f"{task_id}.json", {})


# ------------------------------------------------------------- P1 planning
def plan(coord) -> dict:
    """Evidence-grounded planning: runs the base proposer, then scores
    collected evidence for unresolved work and marks stalled
    fingerprints STOP. Returns the proposal summary."""
    collect_all_terminal(coord)
    res = base_planner.propose(coord)
    d = base_planner._load(coord.root / base_planner.PROPOSALS_FILE)
    st = coord._load()
    # annotate + stall detection
    failed_fp: dict[str, int] = {}
    for p in d["proposals"].values():
        if p.get("status") in ("DISMISSED",):
            continue
        fph = p.get("fingerprint") or _fp(
            p.get("provenance", {}).get("source", "?"),
            p.get("provenance", {}).get("source_task", "?"),
            p.get("prompt_sha", ""))
        p["fingerprint"] = fph
    for p in d["proposals"].values():
        prov_task = p.get("provenance", {}).get("source_task", "")
        tk = st["tasks"].get(prov_task)
        if tk and tk.get("status") == "FAILED" and \
                p.get("prompt_sha") == tk.get("prompt_sha"):
            failed_fp[p["fingerprint"]] = \
                failed_fp.get(p["fingerprint"], 0) + 1
    stopped = []
    for p in d["proposals"].values():
        if p.get("status") == "OPEN" and \
                failed_fp.get(p["fingerprint"], 0) >= STALL_CAP:
            p["status"] = "STOP"
            p["stop_reason"] = ("same unresolved fingerprint failed "
                                f"{failed_fp[p['fingerprint']]}x — "
                                "human rescope required")
            stopped.append(p["proposal_id"])
    if stopped:
        base_planner._save(coord.root / base_planner.PROPOSALS_FILE, d)
    res["stopped"] = stopped
    return res


def new_issue_proposal(coord, kind: str, title: str, prompt: str,
                       worktree: str, signature: str,
                       evidence_refs: list[str], acceptance=None,
                       priority: int = 60) -> dict:
    """Programmatic proposal with explicit issue fingerprint — used by
    grounded backlogs (e.g. audit findings)."""
    d = base_planner._load(coord.root / base_planner.PROPOSALS_FILE)
    if kind in ALWAYS_HUMAN:
        status = "STOP"
        reason = f"kind '{kind}' always requires human action"
    else:
        status, reason = "OPEN", ""
    fp = _fp(kind, evidence_refs and evidence_refs[0] or "", signature)
    for p in d["proposals"].values():
        if p.get("fingerprint") == fp and p.get("status") == "OPEN":
            return {"ok": True, "deduplicated": True,
                    "proposal_id": p["proposal_id"]}
    pid = uuid.uuid4().hex[:10]
    p = {"proposal_id": pid, "status": status, "stop_reason": reason,
         "kind": kind, "fingerprint": fp, "title": title[:160],
         "prompt": prompt, "prompt_sha": prompt_sha(prompt),
         "worktree": str(worktree), "priority": int(priority),
         "depends_on": [], "acceptance": list(acceptance or []),
         "requires_human_approval": True,
         "provenance": {"source": "cdp_issue", "source_task": "",
                        "reason": signature[:400],
                        "evidence_refs": list(evidence_refs),
                        "generated_by": "cdp",
                        "generated_at": utcnow()}}
    d["proposals"][pid] = p
    base_planner._save(coord.root / base_planner.PROPOSALS_FILE, d)
    return {"ok": True, "proposal_id": pid, "status": status}


# ------------------------------------------------------------- P2 handoff
def _load_program(coord) -> dict:
    p = coord.root / PROGRAM_FILE
    prog = read_json(p, {})
    if not prog:
        return {}
    # fail closed on expiry or missing required fields
    if not prog.get("program_id") or not prog.get("worktrees"):
        return {}
    if prog.get("ongoing"):
        if (prog.get("owner_authorized") is not True or
                not isinstance(prog.get("allowed_paths"), list) or
                not prog.get("allowed_paths") or
                not set(prog.get("kinds") or []).issubset(SAFE_KINDS) or
                not prog.get("kinds")):
            return {}
    else:
        exp = float(prog.get("expires_epoch") or 0)
        if exp and time.time() > exp:
            return {}
    from . import trial_scope
    return trial_scope.extend_program(coord.root, prog)


def handoff_tick(coord) -> dict:
    """Auto-promote+dispatch the best OPEN proposal ONLY if it fits an
    unexpired program authorization exactly. Fail closed otherwise."""
    prog = _load_program(coord)
    if not prog:
        return {"handoff": False, "reason": "no valid program file"}
    if prog.get("ongoing"):
        holds = coord.global_holds()
        if holds:
            return {"handoff": False, "reason":
                    "standing mandate paused by guard: " + "; ".join(holds)}
    allowed = {str(Path(w).resolve()).casefold()
               for w in prog.get("worktrees", [])}
    kinds = set(prog.get("kinds", SAFE_KINDS))
    max_tasks = None if prog.get("ongoing") else int(prog.get("max_tasks", 3))
    st = coord._load()
    running = [t for t in st["tasks"].values() if t["status"] in
               ("DISPATCHED", "RUNNING", "VERIFYING", "NEEDS_APPROVAL")]
    if running:
        return {"handoff": False, "reason": f"{running[0]['id']} in flight"}
    done = sum(1 for t in st["tasks"].values()
               if t.get("program_id") == prog["program_id"]
               and t["status"] in ("COMPLETE", "FAILED", "BLOCKED"))
    if max_tasks is not None and done >= max_tasks:
        return {"handoff": False,
                "reason": f"program task budget {max_tasks} exhausted"}
    if prog.get("ongoing"):
        from datetime import datetime, timezone
        def recent_task(task, hours):
            if task.get("program_id") != prog["program_id"]:
                return False
            try:
                started = datetime.fromisoformat(str(task["created_at"]).replace("Z", "+00:00"))
                return 0 <= (datetime.now(timezone.utc) - started).total_seconds() < 3600 * hours
            except (KeyError, ValueError, TypeError):
                return False
        hour_limit = min(max(int(prog.get("max_dispatches_per_hour", 12)), 1), 24)
        recent = [t for t in st["tasks"].values() if recent_task(t, 1)]
        if len(recent) >= hour_limit:
            return {"handoff": False, "reason":
                    f"hourly pacing {len(recent)}/{hour_limit}; resumes automatically"}
        # Recovery children (RCV-*) are the repair path, not new
        # failures — counting them would let a failure storm starve the
        # very mechanism meant to fix it.
        failed = sum(1 for t in st["tasks"].values()
                     if recent_task(t, 24) and t.get("status") == "FAILED"
                     and not str(t.get("id", "")).startswith("RCV-"))
        failure_limit = min(max(int(prog.get("max_failures_per_24h", 8)), 1), 12)
        if failed >= failure_limit:
            return {"handoff": False, "reason":
                    f"failure circuit breaker {failed}/{failure_limit}; needs investigation"}
        # Meter reported model usage; rolling 24h reset, not daily approval.
        token_limit = int(prog.get("max_reported_tokens_per_24h", 1500000))
        if token_limit <= 0:
            return {"handoff": False, "reason": "model usage ceiling not configured"}
        # Discount cached reads conservatively, but retain an independent
        # hard ceiling on all reported tokens to prevent runaway usage.
        raw_limit = int(prog.get("max_raw_reported_tokens_per_24h", token_limit))
        weight = float(prog.get("cached_read_weight", 1.0))
        if raw_limit <= 0 or not 0.5 <= weight <= 1.0:
            return {"handoff": False, "reason": "invalid model usage guard configuration"}
        used, raw_used = 0, 0
        events = coord.root / "coordinator_events.jsonl"
        if events.is_file():
            from collections import deque
            with events.open(encoding="utf-8", errors="replace") as evfile:
                for line in deque(evfile, maxlen=5000):
                    try:
                        event = json.loads(line)
                        if event.get("kind") != "prompt_done":
                            continue
                        task = st["tasks"].get(event.get("task_id")) or {}
                        if task.get("program_id") != prog["program_id"]:
                            continue
                        when = datetime.fromisoformat(str(event["ts"]).replace("Z", "+00:00"))
                        if 0 <= (datetime.now(timezone.utc) - when).total_seconds() < 86400:
                            usage = event.get("usage") or {}
                            total = max(0, int(usage.get("totalTokens", 0)))
                            inp = max(0, int(usage.get("inputTokens", 0)))
                            cached = max(0, min(total, inp, int(usage.get("cachedReadTokens", 0))))
                            raw_used += total
                            used += total - int(cached * (1.0 - weight))
                    except (ValueError, KeyError, TypeError):
                        continue
        if raw_used >= raw_limit:
            return {"handoff": False, "reason":
                    f"rolling 24h HARD raw-token guard {raw_used}/{raw_limit}; auto resets"}
        if used >= token_limit:
            return {"handoff": False, "reason":
                    f"rolling 24h weighted model-usage guard {used}/{token_limit} units "
                    f"(raw {raw_used}, cache weight {weight}); auto resets"}
    # pick highest-priority OPEN proposal inside the program
    cand = None
    for p in base_planner.list_proposals(coord):
        wt = str(Path(p["worktree"]).resolve()).casefold()
        if p.get("status") != "OPEN":
            continue
        if wt not in allowed:
            continue
        # stale reconcile/followup proposals from the old planner can
        # never qualify under an ongoing program (only cdp_issue may) —
        # close them once instead of scanning them as OPEN forever
        if prog.get("ongoing") and \
                (p.get("provenance") or {}).get("source") != "cdp_issue":
            try:
                pd = base_planner._load(
                    coord.root / base_planner.PROPOSALS_FILE)
                rec = pd["proposals"].get(p["proposal_id"])
                if rec and rec.get("status") == "OPEN":
                    rec["status"] = "SUPERSEDED"
                    rec["stop_reason"] = (
                        "non-cdp provenance; recovery pipeline owns "
                        "the parent task")
                    base_planner._save(
                        coord.root / base_planner.PROPOSALS_FILE, pd)
            except Exception:
                pass
            continue
        if p.get("kind", "analyze") not in kinds:
            continue
        if prog.get("ongoing"):
            # Old planner reconcile prompts have already failed repeatedly;
            # only evidence-backed CDP proposals can use standing authority.
            if p.get("provenance", {}).get("source") != "cdp_issue":
                continue
            allowed_paths = [str(x).replace("\\", "/").rstrip("/")
                             for x in prog["allowed_paths"]]
            acceptance = p.get("acceptance") or []
            if not acceptance:
                continue
            if any(not chk.get("path") or
                   Path(str(chk["path"])).is_absolute() or
                   ".." in Path(str(chk["path"])).parts or
                   not any(str(chk["path"]).replace("\\", "/") == x or
                           str(chk["path"]).replace("\\", "/").startswith(x + "/")
                           for x in allowed_paths)
                   for chk in acceptance if chk.get("type") != "test"):
                continue
            if p.get("kind") in ("repair-small", "test-add") and not any(
                    x.get("type") == "test" for x in acceptance):
                continue
        cand = p
        break
    if not cand:
        return {"handoff": False, "reason": "no in-program proposal"}
    res = base_planner.promote(coord, cand["proposal_id"])
    if not res.get("ok"):
        return {"handoff": False, "error": res.get("error")}
    tid = res["task_id"]
    coord._mutate(tid, lambda t: t.__setitem__(
        "program_id", prog["program_id"]))
    # the program file IS the owner's approval for in-scope work —
    # but only for the kinds it lists and worktrees it names.
    coord.approve(tid)
    disp = coord.dispatch(tid)
    coord._event("cdp_handoff", proposal=cand["proposal_id"],
                 task_id=tid, program=prog["program_id"],
                 dispatched=bool(disp.get("dispatched")))
    return {"handoff": bool(disp.get("dispatched")), "task_id": tid,
            "dispatch": disp}


# ------------------------------------------------------------- P3 escalate
def escalate_stops(coord, notifier=None) -> int:
    """ntfy for proposals moved to STOP or tasks that stalled — once
    each (dedup by fingerprint)."""
    from .notify import Notifier
    n = notifier or Notifier(coord.root)
    sent = 0
    for p in base_planner.list_proposals(coord, status=""):
        if p.get("status") == "STOP":
            r = n.task_failed(
                f"Planner STOP: {p['title'][:60]}",
                p.get("stop_reason", "unresolved"),
                "human rescope / decision")
            sent += int(bool(r.get("sent")))
    return sent


# ------------------------------------------------------------- P5 backlog
def build_backlog(coord, worktree: str, doc_paths: list[str]) -> dict:
    """Grounded backlog: read real audit docs, extract candidate repair
    items VERBATIM as proposals (never invented coordinates/quests)."""
    wt = Path(worktree)
    items = []
    for rel in doc_paths:
        p = wt / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            s = line.strip().lstrip("-*0123456789. ").strip()
            if len(s) < 25 or not s:
                continue
            low = s.lower()
            if any(k in low for k in (
                    "todo", "fix", "repair", "missing", "gap",
                    "recommend", "next step", "remaining")):
                items.append({"text": s[:200], "doc": rel})
    out = {"generated_at": utcnow(), "worktree": str(wt),
           "items": items[:40],
           "note": "verbatim extraction only — human must verify "
                   "before any repair task is created"}
    atomic_write_json(coord.root / BACKLOG_FILE, out)
    return out
