"""DevinBrain — the PRIMARY conversational backend for RealJarvis.

One long-lived ACP session ("chat session") carries the full multi-turn
context server-side. RealJarvis's persona/system prompt is injected as
the seed message at session creation; every later user message is a
plain prompt. The session id is persisted in ``chat_session.json`` so a
RealJarvis restart ``session_load``s and keeps the same conversation.

Honesty contract — respond() returns an envelope:
    {"brain": "devin",   "text": ..., "session_id": ...}          real reply
    {"brain": "error",   "error": ...}                            Devin failed
    {"brain": "awaiting_approval", "request_id": ...}             gated action

The orchestrator MUST surface non-"devin" envelopes as a fallback — it
may never present them as a Devin answer.

Tools: the agent reaches RealJarvis capabilities only through the
permission-controlled channel — ``jarvis_tools run`` via terminal/*,
fs read/write inside CHAT_HOME, everything else → policy → ASK →
ApprovalManager (same path as task dispatch approvals).
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .acp_client import AcpError, DevinAcpClient
from .approvals import ApprovalManager
from .bridge_store import (SUBPROCESS_NO_WINDOW, atomic_write_json,
                           read_json, utcnow)
from .notify import Notifier
from .policy import ALLOW, ASK, DENY, classify_request

BRIDGE_ROOT = Path(__file__).resolve().parent
# python -m DevinBridge.jarvis_tools must run with the package's PARENT
# dir as cwd — CHAT_HOME is only the fs workspace. Running from the
# module root fixes the 'tools fail to launch' bug.
MODULE_ROOT = BRIDGE_ROOT.parent
CHAT_HOME = BRIDGE_ROOT / "chat_home"
SESSION_STORE = BRIDGE_ROOT / "chat_session.json"
CHAT_APPROVAL_WAIT_S = float(os.environ.get(
    "DEVIN_CHAT_APPROVAL_WAIT", "120"))

_TOOL_MODULE = "DevinBridge.jarvis_tools"
_MAX_CMD_LEN = 2000
_MAX_ARG_LEN = 4096
_MAX_TERMINALS = 8
_PY_NAMES = {"python", "python.exe", "python3", "python3.exe", "py",
             "py.exe"}


def _is_within(child: Path, parent: Path) -> bool:
    """True path-ancestry check — not a string prefix. resolve() first so
    symlinks/junctions/8.3 names can't escape."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class _Terminals:
    """Minimal ACP terminal/* backend — exact-shape allowlist only.

    Permitted command (parsed argv, no shell):
        <python> -m DevinBridge.jarvis_tools run <name> [--json '<obj>']

    <python> must be a plain python launcher name or sys.executable;
    <name> must exist in jarvis_tools.TOOLS; --json must be a JSON
    object ≤4KB. cwd/env/args overrides from the caller are ignored —
    the subprocess always runs sys.executable from MODULE_ROOT with the
    host environment. Every other request is denied with diagnostics.
    """

    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.run_cwd = MODULE_ROOT
        self.terms: dict[str, dict] = {}
        self.denials: list[dict] = []

    def _deny(self, reason: str) -> None:
        self.denials.append({"ts": utcnow(), "reason": reason[:300]})

    def _allowed(self, params: dict) -> tuple[list[str] | None, str]:
        cmd = str(params.get("command") or "")
        if not cmd.strip():
            return None, "empty command"
        if len(cmd) > _MAX_CMD_LEN:
            return None, "command too long"
        # Host-provided argv fragments/env can't be verified → refuse.
        if params.get("args") or params.get("env"):
            return None, "args/env overrides are not permitted"
        try:
            argv = shlex.split(cmd, posix=True)
        except ValueError as e:
            return None, f"unparseable command: {e}"
        if len(argv) < 5:
            return None, ("expected: python -m DevinBridge.jarvis_tools "
                          "run <tool> [--json '{...}']")
        exe = Path(argv[0]).name.lower()
        if exe not in _PY_NAMES and argv[0] != sys.executable:
            return None, f"interpreter not allowed: {argv[0]}"
        # Two equivalent surfaces the agent actually uses:
        #   python -m DevinBridge.jarvis_tools run <tool> [...]
        #   python run_tool.py run <tool> [...]      (session shim)
        # Both exec the SAME fixed interpreter+module+cwd below.
        if argv[1] == "-m":
            if argv[2] != _TOOL_MODULE:
                return None, f"module must be {_TOOL_MODULE}"
            if argv[3] != "run":
                return None, "only 'run' subcommand is permitted"
            tool, rest = argv[4], argv[5:]
        elif Path(argv[1]).name == "run_tool.py":
            if argv[2] != "run":
                return None, "only 'run' subcommand is permitted"
            tool, rest = argv[3], argv[4:]
        else:
            return None, f"module must be {_TOOL_MODULE} or run_tool.py"
        from . import jarvis_tools
        if tool not in jarvis_tools.TOOLS:
            return None, (f"unknown tool '{tool}'; allowed: "
                          f"{', '.join(sorted(jarvis_tools.TOOLS))}")
        if rest:
            if len(rest) != 2 or rest[0] != "--json":
                return None, "only optional '--json <object>' is allowed"
            if len(rest[1]) > _MAX_ARG_LEN:
                return None, "--json payload too large"
            try:
                parsed = json.loads(rest[1])
            except ValueError:
                return None, "--json payload is not valid JSON"
            if not isinstance(parsed, dict):
                return None, "--json payload must be a JSON object"
        # Exec the FIXED interpreter + module — never the caller's argv0.
        return [sys.executable, "-m", _TOOL_MODULE, "run", tool] + rest, ""

    _MAX_RECORDS = 32   # hard bound on retained terminal entries

    def _live(self) -> int:
        return sum(1 for t in self.terms.values()
                   if t["proc"].poll() is None)

    def _reap(self) -> None:
        """Free slots held by FINISHED processes whose output the agent
        already consumed. Done-but-unread entries stay addressable for
        terminal/output — we never silently eat unread output."""
        for tid, t in list(self.terms.items()):
            if t["proc"].poll() is not None and t.get("buf") is not None:
                self.terms.pop(tid, None)

    def handle(self, method: str, params: dict) -> dict:
        if method == "terminal/create":
            self._reap()
            if self._live() >= _MAX_TERMINALS:
                self._deny(f"{_MAX_TERMINALS} terminals still running")
                raise AcpError(
                    f"terminal limit: {_MAX_TERMINALS} concurrent "
                    "processes — wait_for_exit or release one first",
                    code=-32602)
            if len(self.terms) >= self._MAX_RECORDS:
                self._deny("stale terminal records")
                raise AcpError(
                    "too many finished terminals retained — call "
                    "terminal/release to clear them", code=-32602)
            argv, why = self._allowed(params)
            if argv is None:
                # log the RAW command — the real-world failures were
                # shape mismatches, diagnosable only with the text
                self._deny(f"{why} | cmd: "
                           f"{str(params.get('command') or '')[:160]}")
                raise AcpError(
                    f"terminal blocked: {why}. Allowed form: "
                    "python -m DevinBridge.jarvis_tools run <tool> "
                    "[--json '{...}']", code=-32602)
            try:
                proc = subprocess.Popen(
                    argv, cwd=str(self.run_cwd), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True,
                    errors="replace",
                    creationflags=SUBPROCESS_NO_WINDOW)
            except OSError as e:
                self._deny(f"spawn failed: {e}")
                raise AcpError(f"terminal spawn failed: {e}",
                               code=-32602)
            tid = uuid.uuid4().hex[:16]
            self.terms[tid] = {"proc": proc, "buf": None,
                               "argv": argv[4] if len(argv) > 4 else "",
                               "cwd": str(self.run_cwd)}
            return {"terminalId": tid}
        tid = str(params.get("terminalId") or "")
        t = self.terms.get(tid)
        if not t:
            if method in ("terminal/release", "terminal/kill"):
                return {}  # idempotent — already gone
            raise AcpError("unknown terminal", code=-32602)
        if method == "terminal/output":
            if t["buf"] is None:
                try:
                    out, _ = t["proc"].communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    return {"output": "", "truncated": False,
                            "exitStatus": None,
                            "note": "still running after 120s"}
                t["buf"] = out
            done = t["proc"].poll() is not None
            return {"output": t["buf"][-8000:], "truncated": len(t["buf"]) > 8000,
                    "exitStatus": {"exitCode": t["proc"].returncode}
                    if done else None}
        if method == "terminal/wait_for_exit":
            try:
                rc = t["proc"].wait(timeout=120)
            except subprocess.TimeoutExpired:
                return {"exitCode": None, "signal": None,
                        "timeout": True}
            return {"exitCode": rc, "signal": None}
        if method in ("terminal/release", "terminal/kill"):
            if t["proc"].poll() is None:
                t["proc"].kill()
            self.terms.pop(tid, None)
            return {}
        raise AcpError(f"unsupported {method}", code=-32601)


class ChatToolHandler:
    """agent_request_handler for the chat session."""

    def __init__(self, coord, notifier: Notifier,
                 approvals: ApprovalManager):
        self.coord = coord
        self.notifier = notifier
        self.approvals = approvals
        self.home = CHAT_HOME.resolve()
        self.terms = _Terminals(self.home)

    def _in_home(self, p: str) -> Path:
        """Resolve inside CHAT_HOME with true ancestry — resolve() makes
        symlinks/junctions/.. concrete, then relative_to verifies the
        real path is actually under home (prefix matching is forgeable:
        chat_home2, chat_home.evil, etc.)."""
        rp = Path(p)
        # Accept either notes/file or chat_home/notes/file relative to workspace.
        if not rp.is_absolute() and rp.parts and rp.parts[0].lower() == "chat_home":
            rp = Path(*rp.parts[1:])
        if not rp.is_absolute():
            rp = self.home / rp
        rp = rp.resolve()
        if not _is_within(rp, self.home):
            raise AcpError(f"path outside chat workspace: {p}", code=-32602)
        return rp

    def __call__(self, msg: dict):
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if method == "session/request_permission":
            return {"outcome": self._permission(params)}
        if method.startswith("terminal/"):
            return self.terms.handle(method, params)
        if method in ("fs/read_text_file", "fs/write_text_file"):
            path = self._in_home(str(params.get("path") or ""))
            if method == "fs/read_text_file":
                return {"content": path.read_text(
                    encoding="utf-8", errors="replace")}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(params.get("content") or ""),
                            encoding="utf-8")
            return {}
        raise AcpError(f"host does not implement {method}", code=-32601)

    def _permission(self, params: dict) -> dict:
        options = params.get("options") or []
        cls = classify_request(params, str(self.home))
        if cls["fingerprint"] in self.coord.approved_fingerprints():
            return _pick(options, allow=True)
        if cls["decision"] == ALLOW:
            return _pick(options, allow=True)
        if cls["decision"] == DENY:
            return _pick(options, allow=False)
        # ASK — real record + ONE notification, but chat can't stall for
        # hours: wait CHAT_APPROVAL_WAIT_S then cancel the request. An
        # approved fingerprint auto-passes on retry next turn.
        rec = self.approvals.create(
            task_id="__chat__", session_id=self.coord._chat_sid or "",
            fingerprint=cls["fingerprint"], summary=cls["summary"],
            reason=cls["reason"], tool_call=params.get("toolCall") or {},
            risk="MEDIUM", ttl_s=3600)
        link = self.coord.dashboard_link(rec["request_id"], self.approvals)
        self.notifier.approval_required(
            "RealJarvis chat", cls["summary"], "MEDIUM", link,
            rec["request_id"])
        final = self.approvals.wait_for_decision(
            rec["request_id"], timeout_s=CHAT_APPROVAL_WAIT_S, poll_s=2.0)
        return _pick(options, allow=(final == "APPROVED"))


def _pick(options: list[dict], allow: bool) -> dict:
    want = ("allow_once", "allow_always") if allow else (
        "reject_once", "reject_always")
    for k in want:
        for o in options or []:
            if o.get("kind") == k:
                return {"outcome": "selected", "optionId": o["optionId"]}
    return {"outcome": "cancelled"}


SEED_TEMPLATE = """You are Devin, the primary reasoning brain inside RealJarvis —
the user's Czech JARVIS-style assistant. You answer EVERY user message
through this session.

{persona}

Hard rules:
- Answer naturally and concisely in the user's language (default Czech),
  preserving the persona's tone, humour and honorifics.
- You have NO direct access to the user's machine except the
  whitelisted `jarvis_tools` commands (see TOOLS below). Never claim you
  executed an action that was not actually run.
- File access is limited to the chat workspace {home}. Any other path,
  credential, destructive, publishing or system-mutating action WILL be
  denied or escalated for human approval — do not attempt it silently.
- If you need a permitted action, call it through a terminal tool call
  running: python -m DevinBridge.jarvis_tools run <name> --json {{...}}
- If an action needs human approval it may be cancelled on timeout —
  tell the user it awaits their approval and continue with the rest.

TOOLS available via jarvis_tools:
{tools}
"""


class DevinBrain:
    def __init__(self, coord, persona: str = "", model: str = "swe-2-high"):
        self.coord = coord
        self.model = model
        self.persona = persona
        self.session_path = SESSION_STORE
        self._client = None
        self.approvals = ApprovalManager(coord.root)
        self.notifier = Notifier(coord.root)
        self._seed_pending = ""
        if not hasattr(coord, "_chat_sid"):
            coord._chat_sid = ""

    # ------------------------------------------------------------ client
    def _ensure(self) -> DevinAcpClient:
        if self._client is None or not self._client.is_alive():
            self._client = self.coord._client_factory()
            self._client.start()
            self._client.agent_request_handler = ChatToolHandler(
                self.coord, self.notifier, self.approvals)
        return self._client

    # ------------------------------------------------------------ session
    def _store_load(self) -> dict:
        return read_json(self.session_path, {})

    def _store_save(self, d: dict) -> None:
        atomic_write_json(self.session_path, d)

    def ensure_session(self) -> str:
        """Existing chat session if loadable; otherwise a fresh one,
        seeded with persona + tool rules."""
        client = self._ensure()
        st = self._store_load()
        sid = st.get("session_id", "")
        CHAT_HOME.mkdir(parents=True, exist_ok=True)
        if sid:
            try:
                client.session_load(sid, str(CHAT_HOME))
                self.coord._chat_sid = sid
                return sid
            except Exception:
                pass  # recreate below
        res = client.session_new(str(CHAT_HOME), model=self.model,
                                 mode="smart")
        sid = res.get("sessionId", "")
        if not sid:
            raise RuntimeError("chat session/new returned no sessionId")
        from . import jarvis_tools
        seed = SEED_TEMPLATE.format(
            persona=self.persona or "(Czech JARVIS persona)",
            home=str(CHAT_HOME),
            tools=jarvis_tools.tools_doc())
        self._store_save({"session_id": sid, "created": utcnow(),
                          "model": self.model})
        # The seed rides the FIRST prompt so the agent persona is locked in.
        self.coord._chat_sid = sid
        self._seed_pending = seed
        return sid

    # ------------------------------------------------------------ respond
    def respond(self, user_text: str,
                on_delta: Callable[[str], None] | None = None,
                timeout: float = 240.0) -> dict:
        try:
            sid = self.ensure_session()
        except Exception as e:
            return {"brain": "error", "error": f"session: {e}"}
        seed = getattr(self, "_seed_pending", "")
        text = f"{seed}\n\nUSER: {user_text}" if seed else user_text
        pieces: list[str] = []

        def _collect(upd):
            kind = upd.get("sessionUpdate", "")
            if kind == "agent_message_chunk":
                c = upd.get("content") or {}
                t = c.get("text", "")
                if t:
                    pieces.append(t)
                    if on_delta:
                        on_delta(t)

        try:
            res = self._client.session_prompt(
                sid, text, on_update=_collect, timeout=timeout)
        except Exception as e:
            return {"brain": "error", "session_id": sid,
                    "error": f"prompt: {e}"}
        if seed:
            self._seed_pending = ""
        out = "".join(pieces) or res.text
        return {"brain": "devin", "text": out, "session_id": sid,
                "stop_reason": res.stop_reason, "usage": res.usage}
