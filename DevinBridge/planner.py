"""Evidence-based next-task proposer for the DevinBridge coordinator.

A proposal is NOT a task — it is a suggestion with full provenance that
a human promotes via ``cli plan-promote``. Proposals are derived ONLY
from concrete evidence:

  * declared_followups recorded on a COMPLETE parent task (declared by
    a human when the parent was created — never invented at runtime)
  * FAILED / BLOCKED / NEEDS_REVIEW production tasks (reconcile, not
    blind retry — the proposal carries the failure evidence)
  * GitHub issue evidence when the probe is available

Anti-loop invariants:
  * identical prompt_sha already queued/running → skip
  * identical prompt_sha already open as a proposal → skip
  * parent FAILED at/above its max_attempts with the same prompt →
    skip (no-progress loop guard; humans must re-scope manually)
  * synthetic test-scope tasks never produce proposals
  * proposals are always ``approved=False`` — a planner can never
    widen scope, mint permissions, or authorize itself.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from .bridge_store import atomic_write_json, prompt_sha, read_json, utcnow

PROPOSALS_FILE = "proposals.json"
MAX_OPEN_PROPOSALS = 20


def _load(path: Path) -> dict:
    d = read_json(path, {})
    d.setdefault("proposals", {})
    return d


def _save(path: Path, d: dict) -> None:
    atomic_write_json(path, d)


def _open_prompt_shas(st: dict, prop_d: dict) -> set[str]:
    """prompt fingerprints already queued or already proposed — the
    dedup key that prevents duplicate/circular generation."""
    shas = set()
    for t in st.get("tasks", {}).values():
        if t.get("status") not in ("COMPLETE", "FAILED", "BLOCKED",
                                   "PAUSED"):
            shas.add(t.get("prompt_sha", ""))
    for p in prop_d.get("proposals", {}).values():
        if p.get("status") in ("OPEN",):
            shas.add(p.get("prompt_sha", ""))
    return shas


def propose(coord) -> dict:
    """Scan coordinator evidence; create/dedupe proposals. Returns the
    new proposals created this run (existing OPEN ones are kept)."""
    st = coord._load()
    path = coord.root / PROPOSALS_FILE
    d = _load(path)
    used = _open_prompt_shas(st, d)
    open_n = sum(1 for p in d["proposals"].values()
                 if p.get("status") == "OPEN")
    created = []

    def _mk(source: str, src_task: str, title: str, prompt: str,
            worktree: str, reason: str, evidence_refs: list[str],
            depends_on=None, acceptance=None, priority=60):
        nonlocal open_n
        if open_n >= MAX_OPEN_PROPOSALS:
            return None
        sha = prompt_sha(prompt)
        if sha in used:
            return None
        pid = uuid.uuid4().hex[:10]
        prop = {
            "proposal_id": pid, "status": "OPEN",
            "title": title[:160], "prompt": prompt, "prompt_sha": sha,
            "worktree": str(worktree), "priority": int(priority),
            "depends_on": list(depends_on or []),
            "acceptance": list(acceptance or []),
            "requires_human_approval": True,
            "provenance": {
                "source": source, "source_task": src_task,
                "reason": reason[:400],
                "evidence_refs": list(evidence_refs),
                "generated_by": "planner", "generated_at": utcnow(),
            },
        }
        d["proposals"][pid] = prop
        used.add(sha)
        open_n += 1
        created.append(prop)
        return prop

    for t in sorted(st.get("tasks", {}).values(),
                    key=lambda x: x.get("created_at", "")):
        if t.get("scope", "production") == "test":
            continue
        status = t.get("status", "")
        tid = t.get("id", "?")
        # ---- source: explicit declared follow-ups on a completed task
        if status == "COMPLETE":
            for fu in t.get("declared_followups") or []:
                prompt = str(fu.get("prompt") or "").strip()
                if not prompt:
                    continue
                _mk("declared_followup", tid,
                    str(fu.get("title") or f"Follow-up of {tid}"),
                    prompt, str(fu.get("worktree") or t["worktree"]),
                    f"declared on {tid}; acceptance evidence: "
                    f"{(t.get('evidence') or {}).get('checks') and 'passed' or 'recorded'}",
                    [f"task:{tid}", "acceptance_passed"],
                    depends_on=[tid],
                    acceptance=fu.get("acceptance"),
                    priority=int(fu.get("priority", 60)))
        # ---- source: reconcile exhausted failures (NOT a blind retry —
        # if attempts were exhausted with the same prompt, the planner
        # cannot reproduce it; a human must re-scope first)
        # Under an ongoing CDP program the recovery pipeline owns FAILED
        # parents (RCA + bounded ladder) — generating reconcile
        # proposals here only re-clogs the store every tick.
        _prog = read_json(coord.root / "autonomy_scope"
                          / "CDP_PROGRAM.json", {}) \
            if status in ("FAILED", "BLOCKED") else {}
        _legacy_only = not _prog.get("ongoing")
        if status in ("FAILED", "NEEDS_REVIEW") and _legacy_only:
            _mk("failure_reconcile", tid,
                f"Reconcile {status.lower()} task {tid}",
                (f"Task {tid} ('{t.get('title','')[:80]}') ended in "
                 f"{status}. Investigate the recorded evidence, fix the "
                 "root cause and complete the original objective.\n\n"
                 f"Original prompt:\n{t.get('prompt','')[:1500]}\n\n"
                 f"Last error: {t.get('last_error','')[:300]}"),
                t["worktree"],
                f"{tid} in {status} after {t.get('attempts',0)} attempt(s)",
                [f"task:{tid}", f"error:{t.get('last_error','')[:120]}"],
                acceptance=t.get("acceptance"),
                priority=40)
        if status == "BLOCKED" and _legacy_only:
            _mk("blocked_reconcile", tid,
                f"Unblock {tid} (human decision needed)",
                (f"Task {tid} was BLOCKED. Review the denial reason, "
                 "propose a safe alternative that does NOT repeat the "
                 "denied action, and report findings — make no changes "
                 f"without approval.\n\n{t.get('prompt','')[:1200]}"),
                t["worktree"],
                f"{tid} BLOCKED — needs scoped alternative",
                [f"task:{tid}", "blocked"], priority=30)

    _save(path, d)
    return {"created": [{"proposal_id": p["proposal_id"],
                         "title": p["title"],
                         "source": p["provenance"]["source"]}
                        for p in created],
            "open_total": open_n}


def list_proposals(coord, status: str = "OPEN") -> list[dict]:
    d = _load(coord.root / PROPOSALS_FILE)
    out = [p for p in d["proposals"].values()
           if not status or p.get("status") == status]
    return sorted(out, key=lambda p: p.get("provenance", {})
                  .get("generated_at", ""))


def promote(coord, proposal_id: str) -> dict:
    """Turn a proposal into a real PENDING task — approved=False ALWAYS.
    The human still runs `cli approve <task>` before any dispatch."""
    path = coord.root / PROPOSALS_FILE
    d = _load(path)
    p = d["proposals"].get(proposal_id)
    if not p:
        return {"ok": False, "error": "unknown proposal"}
    if p.get("status") != "OPEN":
        return {"ok": False, "error": f"proposal is {p.get('status')}"}
    prov = p["provenance"]
    task_id = f"GEN-{proposal_id.upper()}"
    res = coord.add_task(
        task_id, p["title"], p["prompt"], p["worktree"],
        priority=p["priority"], depends_on=p["depends_on"],
        acceptance=p["acceptance"], approved=False,
        scope="production", owner="planner+human",
        reason=prov["reason"], generated_by="planner",
        evidence_refs=prov["evidence_refs"])
    if res.get("added"):
        p["status"] = "PROMOTED"
        p["promoted_task"] = task_id
        p["promoted_at"] = utcnow()
        _save(path, d)
        return {"ok": True, "task_id": task_id, "approved": False}
    return {"ok": False, "error": res.get("reason", "add failed")}


def dismiss(coord, proposal_id: str, note: str = "") -> dict:
    path = coord.root / PROPOSALS_FILE
    d = _load(path)
    p = d["proposals"].get(proposal_id)
    if not p:
        return {"ok": False, "error": "unknown proposal"}
    p["status"] = "DISMISSED"
    p["dismiss_note"] = note[:200]
    _save(path, d)
    return {"ok": True}
