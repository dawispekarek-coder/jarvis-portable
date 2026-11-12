"""Detached prompt worker — owns ONE dispatch's agent turn.

Spawned by Coordinator.dispatch()/_spawn_worker as a detached process:

    python -m DevinBridge.prompt_worker <task_id> [--followup MSG]

It session_load()s the recorded session, installs the agent-request
handler, prompts, then verifies. While running:

- ``fs/read_text_file|write_text_file`` → served, scoped to the worktree.
- ``terminal/*`` → refused (the agent has its own exec path).
- ``session/request_permission`` → classified by policy.py:
    ALLOW_ONCE → answered immediately (in-workspace edits, safe commands)
    DENY       → rejected outright (publish/destructive/credentials/…)
    ASK_HUMAN  → ApprovalManager record + task NEEDS_APPROVAL + ONE ntfy
                 → worker blocks polling the store → on APPROVED answers
                 the SAME live request → Devin continues the same turn;
                 on REJECTED/EXPIRED answers cancelled.

A killed worker ends the turn un-answered → tick reconciles the task to
NEEDS_REVIEW (session context still resumable via --followup).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

from .acp_client import AcpError
from .approvals import ApprovalManager
from .bridge_store import atomic_write_json, utcnow
from .daemon import load_config, make_coordinator
from .notify import Notifier
from .policy import ALLOW, ASK, DENY, classify_request

RUNS = Path(__file__).resolve().parent / "runs"
PROMPT_TIMEOUT = 4 * 3600
WAIT_POLL_S = 2.0


def _beat(task_id: str, payload: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    payload["ts"] = utcnow()
    atomic_write_json(RUNS / f"{task_id}.live.json", payload)


def _option(options: list[dict], kind: str) -> str | None:
    for o in options or []:
        if o.get("kind") == kind:
            return o.get("optionId")
    return None


def _reject_outcome(options: list[dict]) -> dict:
    oid = _option(options, "reject_once") or _option(options, "reject_always")
    if oid:
        return {"outcome": "selected", "optionId": oid}
    return {"outcome": "cancelled"}


def _allow_outcome(options: list[dict]) -> dict:
    # Never allow_always — per-action scope only.
    oid = _option(options, "allow_once") or _option(options, "allow_always")
    if oid:
        return {"outcome": "selected", "optionId": oid}
    return {"outcome": "cancelled"}


class Handler:
    """agent_request_handler callback bound to one task's context."""

    def __init__(self, coord, task: dict, approvals: ApprovalManager,
                 notifier: Notifier):
        self.coord = coord
        self.task = task
        self.approvals = approvals
        self.notifier = notifier
        self.worktree = str(Path(task["worktree"]).resolve()).lower()

    # ------------------------------------------------------------- entry
    # ----------------------------------------------------- terminals
    # Bounded terminal/* for ACP workers. Only `python` invocations whose
    # script (or -m module) resolves INSIDE the task worktree run; cwd is
    # forced into the worktree; output is capped; processes are reaped.
    _TERM_MODULES = {"unittest", "pytest"}
    _TERM_MAX_LIVE = 4
    _TERM_BUF = 512 * 1024

    def _terms(self):
        if not hasattr(self, "_term_state"):
            self._term_state = {}
        return self._term_state

    def _terminal_create(self, params: dict) -> dict:
        import shlex
        import subprocess
        cmd = params.get("command") or ""
        args = params.get("args") or []
        if isinstance(args, str):
            args = shlex.split(args)
        exe = Path(cmd).name.lower()
        if exe not in ("python", "python3", "py", "python.exe"):
            raise AcpError(f"terminal: only python is allowed, got {cmd}",
                           code=-32602)
        target = None
        for i, a in enumerate(args):
            if a == "-m":
                mod = args[i + 1] if i + 1 < len(args) else ""
                if mod.split(".")[0] not in self._TERM_MODULES:
                    raise AcpError(
                        f"terminal: -m {mod} not in {self._TERM_MODULES}",
                        code=-32602)
                target = f"module:{mod}"
                break
            if not a.startswith("-"):
                rp = Path(a)
                if not rp.is_absolute():
                    rp = Path(self.task["worktree"]) / a
                rp = rp.resolve()
                if not (str(rp).lower().startswith(self.worktree + os.sep)
                        or str(rp).lower() == self.worktree):
                    raise AcpError(
                        f"terminal: script outside worktree: {a}",
                        code=-32602)
                target = str(rp)
                break
        if target is None:
            raise AcpError("terminal: no script/module to run",
                           code=-32602)
        live = [t for t in self._terms().values()
                if t["proc"].poll() is None]
        if len(live) >= self._TERM_MAX_LIVE:
            raise AcpError("terminal: live terminal cap reached",
                           code=-32603)
        import threading
        import uuid
        tid = uuid.uuid4().hex[:12]
        try:
            proc = subprocess.Popen(
                [cmd] + list(args), cwd=str(self.task["worktree"]),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env={"PATH": os.environ.get("PATH", ""),
                     "PYTHONIOENCODING": "utf-8",
                     "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                     "WINDIR": os.environ.get("WINDIR", "")},
                creationflags=0x08000000)
        except OSError as e:
            raise AcpError(f"terminal spawn failed: {e}", code=-32603)
        buf = bytearray()

        def drain():
            try:
                while True:
                    chunk = proc.stdout.read(65536)  # type: ignore
                    if not chunk:
                        break
                    if len(buf) < self._TERM_BUF:
                        buf.extend(chunk[:self._TERM_BUF - len(buf)])
            except Exception:
                pass
        th = threading.Thread(target=drain, daemon=True)
        th.start()
        self._terms()[tid] = {"proc": proc, "buf": buf, "th": th}
        return {"terminalId": tid}

    def _terminal_output(self, params: dict) -> dict:
        t = self._terms().get(params.get("terminalId", ""))
        if not t:
            raise AcpError("unknown terminalId", code=-32602)
        t["th"].join(timeout=0.5)
        out = bytes(t["buf"]).decode("utf-8", "replace")
        code = t["proc"].poll()
        res: dict = {"output": out,
                     "truncated": len(t["buf"]) >= self._TERM_BUF}
        if code is not None:
            res["exitStatus"] = {"exitCode": code, "signal": None}
        return res

    def _terminal_wait(self, params: dict) -> dict:
        t = self._terms().get(params.get("terminalId", ""))
        if not t:
            raise AcpError("unknown terminalId", code=-32602)
        try:
            code = t["proc"].wait(timeout=float(params.get("timeout", 120)))
        except Exception:
            raise AcpError("wait timed out", code=-32603)
        return {"exitCode": code, "signal": None}

    def _terminal_drop(self, params: dict, kill: bool) -> dict:
        tid = params.get("terminalId", "")
        t = self._terms().pop(tid, None)
        if t:
            if kill and t["proc"].poll() is None:
                t["proc"].kill()
        return {}

    def _terminal(self, method: str, params: dict):
        if method == "terminal/create":
            return self._terminal_create(params)
        if method == "terminal/output":
            return self._terminal_output(params)
        if method == "terminal/wait_for_exit":
            return self._terminal_wait(params)
        if method == "terminal/kill":
            return self._terminal_drop(params, kill=True)
        if method == "terminal/release":
            return self._terminal_drop(params, kill=False)
        raise AcpError(f"host does not implement {method}", code=-32601)

    def __call__(self, msg: dict):
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if method == "session/request_permission":
            return self._permission(params)
        if method in ("fs/read_text_file", "fs/write_text_file"):
            return self._fs(method, params)
        if method.startswith("terminal/"):
            return self._terminal(method, params)
        raise AcpError(f"host does not implement {method}", code=-32601)

    # --------------------------------------------------------------- fs
    def _in_worktree(self, p: str) -> Path:
        rp = Path(p)
        if not rp.is_absolute():
            rp = Path(self.task["worktree"]) / p
        rp = rp.resolve()
        low = str(rp).lower()
        if low.startswith(self.worktree + os.sep) or low == self.worktree:
            return rp
        # Outside the workspace — allowed ONLY if a human-approved
        # request explicitly granted this exact path.
        if low in self.approvals.granted_paths(self.task["id"]):
            self.coord._event("granted_path_write", task_id=self.task["id"],
                              path=str(rp))
            return rp
        # The 24h owner trial never queues approvals for forbidden external
        # writes. Reject the request immediately so route work can continue.
        if self.task.get("program_id"):
            from . import cdp
            grant = cdp._load_program(self.coord)
            if (grant.get("trial_active") and
                    grant.get("program_id") == self.task["program_id"]):
                self.coord._event("trial_out_of_scope_denied",
                                  task_id=self.task["id"], path=str(rp))
                raise AcpError("24h route trial: path outside workspace; "
                               "use authorized worktree instead", code=-32602)
        # The real Devin runtime escalates scope grants internally and
        # calls fs/write directly — the host's denial IS the supported
        # permission boundary. Record it as a pending approval so the
        # human can grant THIS exact path; the agent is denied for now
        # and can retry after approval (resume_task follow-up).
        fp = hashlib.sha256(
            f"fs-write|{low}".encode()).hexdigest()[:20]
        rec = self.approvals.create(
            task_id=self.task["id"],
            session_id=self.task.get("session_id", ""),
            fingerprint=fp,
            summary=f"write outside workspace: {rp.name}",
            reason=f"fs/write to out-of-scope path {rp}",
            tool_call={"kind": "edit",
                       "locations": [{"path": str(rp)}]}, risk="HIGH")
        if rec["status"] == "PENDING" and rec.get("seen_count", 1) <= 1:
            self.coord.mark_needs_approval(
                self.task["id"],
                {"request_id": rec["request_id"], "fingerprint": fp,
                 "summary": f"write outside workspace: {rp}"})
            link = self.coord.dashboard_link(rec["request_id"],
                                             self.approvals)
            self.notifier.approval_required(
                self.task["title"], f"write outside workspace: {rp.name}",
                "HIGH", link, rec["request_id"])
        raise AcpError(f"path outside approved workspace: {p} — "
                       f"human approval requested (dashboard/ntfy)",
                       code=-32602)

    def _fs(self, method: str, params: dict):
        path = self._in_worktree(str(params.get("path") or ""))
        if method == "fs/read_text_file":
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                raise AcpError(f"read failed: {e}", code=-32603)
            line, limit = params.get("line"), params.get("limit")
            if line or limit:
                lines = text.splitlines()
                start = max(int(line or 1) - 1, 0)
                text = "\n".join(lines[start:start + int(limit or len(lines))])
            return {"content": text}
        if not self._program_write_allowed(path):
            raise AcpError("CDP write not authorized by scope/path grant",
                           code=-32602)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(params.get("content") or ""), encoding="utf-8")
        return {}

    def _program_write_allowed(self, path: Path) -> bool:
        """Grant-bound paths for CDP workers; forbidden DB files never writable."""
        try:
            rel = path.resolve().relative_to(Path(self.task["worktree"]).resolve())
        except ValueError:
            return False
        relative = rel.as_posix().casefold()
        if relative in ("db/forever/quest.lua", "db/forever/xp.lua"):
            return False
        program_id = self.task.get("program_id")
        if not program_id:
            return True
        from . import cdp
        grant = cdp._load_program(self.coord)
        if grant.get("program_id") != program_id:
            return False
        if not grant.get("ongoing"):
            return True  # legacy bounded grants; still forbid the two DB files
        allowed = [str(x).replace("\\", "/").strip("/").casefold()
                   for x in grant.get("allowed_paths", [])]
        return any(relative == p or relative.startswith(p + "/")
                   for p in allowed)
    # -------------------------------------------------------- permission
    def _permission(self, params: dict) -> dict:
        options = params.get("options") or []
        tid, sid = self.task["id"], self.task.get("session_id", "")
        tc = params.get("toolCall") or {}
        if tc.get("kind") in ("edit", "move"):
            locs = [x.get("path") for x in (tc.get("locations") or [])
                    if isinstance(x, dict) and x.get("path")]
            for loc in locs:
                candidate = Path(str(loc))
                if not candidate.is_absolute():
                    candidate = Path(self.task["worktree"]) / candidate
                if not self._program_write_allowed(candidate):
                    self.coord._event("scope_write_denied", task_id=tid,
                                      path=str(candidate))
                    return {"outcome": _reject_outcome(options)}
        cls = classify_request(params, self.task["worktree"])
        self.coord._event("permission_request", task_id=tid,
                          decision=cls["decision"], summary=cls["summary"],
                          reason=cls["reason"],
                          tool_call=json.dumps(params.get("toolCall")
                                               or {})[:600])

        # already-approved fingerprint → straight through (post-resume retry)
        if cls["fingerprint"] in self.coord.approved_fingerprints():
            return {"outcome": _allow_outcome(options)}

        if cls["decision"] == ALLOW:
            return {"outcome": _allow_outcome(options)}

        if cls["decision"] == DENY:
            self.coord._event("permission_denied", task_id=tid,
                              summary=cls["summary"], reason=cls["reason"])
            return {"outcome": _reject_outcome(options)}

        # ASK — persist, notify once, block this request until decided.
        risk = ("HIGH" if "outside" in cls["reason"] or "delete"
                in cls["reason"] else "MEDIUM")
        rec = self.approvals.create(
            task_id=tid, session_id=sid, fingerprint=cls["fingerprint"],
            summary=cls["summary"], reason=cls["reason"],
            tool_call=params.get("toolCall") or {}, risk=risk)
        self.coord.mark_needs_approval(
            tid, {"request_id": rec["request_id"], **cls})
        link = self.coord.dashboard_link(rec["request_id"],
                                         self.approvals)
        self.notifier.approval_required(
            self.task["title"], cls["summary"], risk, link,
            rec["request_id"])
        _beat(tid, {"state": "awaiting_approval",
                    "request_id": rec["request_id"], "pid": os.getpid()})
        final = self.approvals.wait_for_decision(
            rec["request_id"], timeout_s=24 * 3600,
            poll_s=WAIT_POLL_S)
        self.coord._event("approval_resolved", task_id=tid,
                          request_id=rec["request_id"], outcome=final)
        if final == "APPROVED":
            self.coord._mutate(
                tid, lambda t: t.__setitem__("status", "RUNNING"))
            return {"outcome": _allow_outcome(options)}
        if final == "REJECTED":
            self.coord._transition(
                tid, "BLOCKED", reason=f"human rejected: {cls['summary']}")
        else:
            self.coord._transition(
                tid, "NEEDS_REVIEW",
                reason=f"approval expired: {cls['summary']}")
        return {"outcome": _reject_outcome(options)}


# ------------------------------------------------------------------ main
def run(task_id: str, followup: str = "") -> int:
    return run_with(make_coordinator(load_config()), task_id, followup)


def run_with(coord, task_id: str, followup: str = "") -> int:
    """Prompt-worker core on a given coordinator — detached process calls
    run(); tests call this in a thread with an injected fake client."""
    t = coord.get_task(task_id)
    if not t:
        print(f"unknown task {task_id}")
        return 2
    # Own ACP client per worker — a blocked prompt (e.g. waiting on a
    # human approval) must not serialize other tasks' short RPCs through
    # one subprocess.
    try:
        client = coord._client_factory()
        client.start()
    except Exception as e:
        coord._on_prompt_error(task_id, t.get("session_id", "?"), e)
        return 1

    client.agent_request_handler = Handler(
        coord, t, ApprovalManager(coord.root),
        Notifier(coord.root))
    try:
        sid = t.get("session_id")
        loaded = False
        if sid:
            # Follow-up/resume: load the persisted session (only sessions
            # that already ran a turn exist in sessions.db).
            try:
                client.session_load(sid, t["worktree"])
                loaded = True
            except Exception as e:
                coord._event("worker_load_failed", task_id=task_id,
                             session_id=sid, error=str(e)[:300])
        if not loaded:
            # First turn (or dead session): create the session HERE — the
            # only process that will ever need it without a prior
            # persisted turn.
            res = client.session_new(
                t["worktree"], model=coord.model,
                mode=t.get("session_mode") or
                getattr(coord, "session_mode", "smart"))
            sid = res.get("sessionId", "")
            if not sid:
                raise RuntimeError(f"session/new returned no id: {res}")
            coord._attach_session(task_id, sid)
            t["session_id"] = sid

        _beat(task_id, {"state": "running", "session_id": sid,
                        "pid": os.getpid(),
                        "followup": bool(followup)})
        prompt = followup or t["prompt"]
        if t.get("program_id"):
            from . import cdp
            grant = cdp._load_program(coord)
            if (grant.get("trial_active") and
                    grant.get("program_id") == t["program_id"]):
                prompt = (
                    "OWNER-APPROVED 24H ROUTE DEVELOPMENT TRIAL. "
                    "Operate ONLY inside the assigned ForeverRoute worktree "
                    "and permitted path list. Do NOT write DevinBridge root "
                    "state/configuration, queued_prompts or approval files, "
                    "installed WoW, SavedVariables, credentials, or protected "
                    "DB/forever/quest.lua and xp.lua. Do not publish/push/merge. "
                    "Outside-worktree writes are DENIED, not awaiting approval. "
                    "If a step cannot be done in-scope, document the blocker "
                    "and continue independent permitted work. Run tests, "
                    "record concrete evidence; avoid false PASS. End your "
                    "report with exactly one verdict line: 'VERDICT: VERIFIED' "
                    "when you produced and checked the evidence, "
                    "'VERDICT: FAILED' when a check failed, or "
                    "'VERDICT: UNKNOWN' when you could not verify.\n\n" + prompt)

        def on_update(upd):
            _beat(task_id, {"state": "running", "session_id": sid,
                            "pid": os.getpid(),
                            "last_update": upd.get("sessionUpdate", "")})
        try:
            res = client.session_prompt(sid, prompt, on_update=on_update,
                                        timeout=PROMPT_TIMEOUT)
        except Exception as e:
            atomic_write_json(RUNS / f"{task_id}.result.json",
                              {"ok": False, "error": str(e)[:500],
                               "ts": utcnow()})
            coord._on_prompt_error(task_id, sid, e)
            return 1

        atomic_write_json(RUNS / f"{task_id}.result.json",
                          {"ok": True, "stop_reason": res.stop_reason,
                           "usage": res.usage,
                           "text_tail": res.text[-2000:], "ts": utcnow()})
        coord._on_prompt_done(task_id, sid, res)
        _beat(task_id, {"state": "done",
                        "stop_reason": res.stop_reason})
        return 0
    finally:
        try:
            client.stop()
        except Exception:
            pass


if __name__ == "__main__":
    _argv = sys.argv[1:]
    _follow = ""
    if "--followup" in _argv:
        i = _argv.index("--followup")
        _follow = _argv[i + 1] if i + 1 < len(_argv) else ""
        _argv = _argv[:i]
    sys.exit(run(_argv[0], _follow))
