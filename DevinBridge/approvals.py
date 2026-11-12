"""Persistent approval queue — survives restarts, single-use decisions.

Records live in ``approval_requests.json`` (atomic writes, file-locked).
Each request has a durable ``request_id``; the ntfy message carries a
short-lived, single-use ``link_token`` that redeems a dashboard session —
no reusable approval secret ever travels inside an ntfy URL.

Decision flow: the pending ACP ``session/request_permission`` stays open
inside the prompt worker. The worker polls this store; the dashboard/CLI
writes the decision; the worker then answers the SAME request — Devin
continues in the same turn, no re-dispatch, no duplicated work.
"""
from __future__ import annotations

import json
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from .bridge_store import (append_jsonl, atomic_write_json,
                           file_lock, read_json, utcnow)

STATUSES = {"PENDING", "APPROVED", "REJECTED", "EXPIRED"}

DEFAULT_TTL_S = 24 * 3600
LINK_TOKEN_TTL_S = 30 * 60


def _extract_paths(tool_call: dict) -> list[str]:
    """Pull absolute paths out of a permission-request toolCall."""
    out: list[str] = []
    for loc in tool_call.get("locations") or []:
        p = str(loc.get("path") or loc or "")
        if p and (":\\" in p or p.startswith("/")):
            out.append(str(Path(p)))
    raw = tool_call.get("rawInput") or {}
    for key in ("path", "file", "filename", "filePath", "file_path",
                "target", "destination"):
        p = str(raw.get(key) or "")
        if p and (":\\" in p or p.startswith("/")):
            out.append(str(Path(p)))
    return out


class ApprovalManager:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "approval_requests.json"
        self.lock = self.root / ".approvals.lock"
        self.audit = self.root / "approval_audit.jsonl"
        self.tokens_path = self.root / "link_tokens.json"

    # ------------------------------------------------------------ store
    def _load(self) -> dict:
        d = read_json(self.path, {})
        d.setdefault("requests", {})
        return d

    def _save(self, st: dict) -> None:
        atomic_write_json(self.path, st)

    def _audit(self, action: str, **kw) -> None:
        append_jsonl(self.audit, {"ts": utcnow(), "action": action, **kw})

    # ---------------------------------------------------------- requests
    def create(self, task_id: str, session_id: str, fingerprint: str,
               summary: str, reason: str, tool_call: dict,
               risk: str, ttl_s: int = DEFAULT_TTL_S) -> dict:
        """Register a pending request — idempotent on
        (task_id, fingerprint): a retried request returns the existing
        record so we never double-notify."""
        with file_lock(self.lock):
            st = self._load()
            for r in st["requests"].values():
                if (r["task_id"] == task_id and
                        r["fingerprint"] == fingerprint and
                        r["status"] == "PENDING"):
                    r["seen_count"] = int(r.get("seen_count", 1)) + 1
                    self._save(st)
                    return r
            now = time.time()
            rec = {
                "request_id": uuid.uuid4().hex[:12],
                "task_id": task_id, "session_id": session_id,
                "fingerprint": fingerprint, "summary": summary[:200],
                "reason": reason[:300], "tool_call": tool_call,
                # Absolute paths the human implicitly approves by
                # approving this request (extracted from the toolCall).
                "paths": _extract_paths(tool_call),
                "risk": risk, "status": "PENDING",
                "created_at": utcnow(), "expires_at_epoch": now + ttl_s,
                "seen_count": 1,
                "decision": None, "decided_at": None, "decided_by": None,
            }
            st["requests"][rec["request_id"]] = rec
            self._save(st)
        self._audit("created", request_id=rec["request_id"],
                    task_id=task_id, risk=risk, summary=rec["summary"])
        return rec

    def get(self, request_id: str) -> dict | None:
        return self._load()["requests"].get(request_id)

    def pending(self) -> list[dict]:
        self.sweep_expired()
        return [r for r in self._load()["requests"].values()
                if r["status"] == "PENDING"]

    def find_pending_for(self, task_id: str, fingerprint: str) -> dict | None:
        for r in self.pending():
            if r["task_id"] == task_id and r["fingerprint"] == fingerprint:
                return r
        return None

    def batch_pending(self) -> dict:
        """Group pending requests by task — repeated high-risk asks from
        one task become ONE batch a decider resolves in a single call,
        instead of an approval drip-feed."""
        groups: dict[str, list[str]] = {}
        for r in self.pending():
            groups.setdefault(str(r.get("task_id") or "?"), []).append(
                r["request_id"])
        return {k: v for k, v in groups.items() if v}

    def decide_batch(self, task_id: str, approved: bool,
                     decided_by: str) -> dict:
        """One decision for every pending request of a task — audited
        as a batch so the scope is explicit, not N separate approvals."""
        ids = self.batch_pending().get(task_id) or []
        if not ids:
            return {"ok": False, "error": f"no pending requests for {task_id}"}
        results = [self.decide(rid, approved,
                               f"{decided_by} (batch:{len(ids)} tasks' requests)")
                   for rid in ids]
        ok_n = sum(1 for r in results if r.get("ok") or r.get("decided"))
        self._audit("batch_decision", task_id=task_id, count=len(ids),
                    applied=ok_n, approved=approved,
                    decided_by=decided_by)
        return {"ok": True, "decided": ok_n, "total": len(ids),
                "approved": approved}

    # ---------------------------------------------------------- decisions
    def decide(self, request_id: str, approved: bool, decided_by: str,
               expected_session: str = "", expected_fp: str = "") -> dict:
        """Human decision — atomic, single-use, staleness-checked."""
        with file_lock(self.lock):
            st = self._load()
            rec = st["requests"].get(request_id)
            if not rec:
                return {"ok": False, "error": "unknown request"}
            if rec["status"] != "PENDING":
                return {"ok": False, "error":
                        f"already {rec['status']} — stale decision rejected",
                        "status": rec["status"]}
            if time.time() > float(rec["expires_at_epoch"]):
                rec["status"] = "EXPIRED"
                self._save(st)
                self._audit("expired_at_decide", request_id=request_id)
                return {"ok": False, "error": "request expired",
                        "status": "EXPIRED"}
            if expected_session and rec["session_id"] != expected_session:
                return {"ok": False, "error": "session mismatch — "
                        "refusing to approve a different context"}
            if expected_fp and rec["fingerprint"] != expected_fp:
                return {"ok": False, "error": "action fingerprint mismatch"}
            rec["status"] = "APPROVED" if approved else "REJECTED"
            rec["decision"] = "approved" if approved else "rejected"
            rec["decided_at"] = utcnow()
            rec["decided_by"] = decided_by[:80]
            self._save(st)
        self._audit("decided", request_id=request_id,
                    decision=rec["decision"], by=decided_by[:80])
        return {"ok": True, "status": rec["status"], "record": rec}

    def sweep_expired(self) -> int:
        now = time.time()
        n = 0
        with file_lock(self.lock):
            st = self._load()
            for rec in st["requests"].values():
                if (rec["status"] == "PENDING" and
                        now > float(rec["expires_at_epoch"])):
                    rec["status"] = "EXPIRED"
                    n += 1
            if n:
                self._save(st)
        for rec in self._load()["requests"].values():
            if rec["status"] == "EXPIRED":
                self._audit("expired", request_id=rec["request_id"])
        return n

    def _delegated_verdict(self, rec: dict) -> bool | None:
        """Owner-delegated self-decision while the 24h trial is active.
        Jarvis approves ordinary work requests and REJECTS anything
        matching credential/publish/protected/destructive patterns —
        delegation is not a blanket approve."""
        from . import trial_scope
        trial = trial_scope.read_trial(self.root) \
            if hasattr(trial_scope, "read_trial") else read_json(
                Path(self.root) / trial_scope.TRIAL, {})
        if not (trial.get("delegate_approvals") and
                float(trial.get("expires_epoch", 0)) > time.time()):
            return None
        from .policy import (DENY_CMD_RE, CREDENTIAL_PATH_RE,
                             PROTECTED_REPO_PATH_RE)
        blob = json.dumps({k: rec.get(k) for k in
                           ("summary", "reason", "tool_call")},
                          default=str)
        return not (DENY_CMD_RE.search(blob) or
                    CREDENTIAL_PATH_RE.search(blob) or
                    PROTECTED_REPO_PATH_RE.search(blob))

    def wait_for_decision(self, request_id: str,
                          timeout_s: float = 3600,
                          poll_s: float = 1.5) -> str:
        """Worker-side blocking wait: returns final status."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            rec = self.get(request_id)
            if not rec:
                return "EXPIRED"
            if rec["status"] != "PENDING":
                return rec["status"]
            verdict = self._delegated_verdict(rec)
            if verdict is not None:
                dec = self.decide(
                    request_id, approved=verdict,
                    decided_by="delegated:trial-24h")
                if dec.get("ok"):
                    return dec["status"]
            time.sleep(poll_s)
        return "EXPIRED"

    def granted_paths(self, task_id: str = "") -> set[str]:
        """Absolute paths explicitly granted by APPROVED requests —
        lets an approved out-of-workspace write succeed for exactly the
        path the human reviewed, nothing else."""
        out: set[str] = set()
        for r in self._load()["requests"].values():
            if r["status"] == "APPROVED" and (
                    not task_id or r["task_id"] == task_id):
                out.update(str(p).lower() for p in r.get("paths", []))
        return out

    # ------------------------------------------------------ link tokens
    def mint_link_token(self, request_id: str) -> str:
        """Single-use, short-lived login token for the dashboard URL
        inside an ntfy message. NOT itself authorization to decide."""
        tok = secrets.token_urlsafe(24)
        with file_lock(self.lock):
            d = read_json(self.tokens_path, {})
            d[tok] = {"request_id": request_id,
                      "created_epoch": time.time()}
            # prune old
            cutoff = time.time() - LINK_TOKEN_TTL_S * 4
            d = {k: v for k, v in d.items()
                 if v["created_epoch"] > cutoff}
            atomic_write_json(self.tokens_path, d)
        self._audit("link_token_minted", request_id=request_id)
        return tok

    def redeem_link_token(self, tok: str) -> str | None:
        """Consume a link token (single-use). Returns request_id or None."""
        with file_lock(self.lock):
            d = read_json(self.tokens_path, {})
            entry = d.pop(tok, None)
            atomic_write_json(self.tokens_path, d)
        if not entry:
            return None
        if time.time() - entry["created_epoch"] > LINK_TOKEN_TTL_S:
            self._audit("link_token_expired_redeem", request_id="?")
            return None
        self._audit("link_token_redeemed",
                    request_id=entry["request_id"])
        return entry["request_id"]
