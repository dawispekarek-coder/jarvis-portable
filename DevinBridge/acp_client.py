"""Devin ACP (Agent Client Protocol) client — JSON-RPC over stdio.

Officially supported interface: spawns ``devin acp`` and speaks ACP.
No UIAutomation, no window scraping, no simulated input.

Authentication is explicit through the ACP ``authenticate`` method —
the host supplies an API key (``_meta.api_key``) exactly as ACP-aware
editors (Windsurf/Zed) do. The key is sourced from:
  1. ``DEVIN_ACP_API_KEY`` / ``DEVIN_API_KEY`` environment variable, or
  2. the installed CLI's own credential file (``credentials.toml``,
     ``windsurf_api_key``) — the same key the local agent itself uses;
     read-only, never logged, never sent anywhere except the local
     ``devin acp`` process over its own stdin pipe.
If neither exists, :meth:`start` raises :class:`AcpAuthRequired` and the
caller must tell the user to authenticate — never fake it.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEVIN_EXE = os.environ.get(
    "DEVIN_ACP_EXE",
    r"C:\Users\Dawis\AppData\Local\Programs\Devin\resources\app"
    r"\extensions\windsurf\devin\bin\devin.exe",
)
CREDENTIALS_TOML = Path(os.environ.get(
    "DEVIN_ACP_CREDENTIALS",
    os.path.expandvars(r"%APPDATA%\devin\credentials.toml")))

PROTOCOL_VERSION = 1


class AcpError(Exception):
    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class AcpAuthRequired(AcpError):
    pass


class AcpTransportError(AcpError):
    pass


def _read_stored_api_key() -> str:
    """Return an API key from env, else the CLI's own credential file.

    Never logs the value. Returns "" when nothing usable is configured.
    """
    for env in ("DEVIN_ACP_API_KEY", "DEVIN_API_KEY"):
        v = os.environ.get(env, "").strip()
        if v:
            return v
    try:
        text = CREDENTIALS_TOML.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r'windsurf_api_key\s*=\s*["\']([^"\']+)', text)
    return m.group(1).strip() if m else ""


@dataclass
class PromptResult:
    stop_reason: str
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    thought: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    user_message_id: str = ""
    raw_updates: int = 0


class DevinAcpClient:
    """Minimal resilient ACP client over a ``devin acp`` stdio child.

    One client = one ``devin acp`` process = any number of sessions.
    ``on_notification`` receives raw ``session/update`` dicts for progress
    reporting; a default collector is kept per-prompt.
    """

    def __init__(self, exe: str = DEVIN_EXE, api_key: str | None = None,
                 extra_env: dict[str, str] | None = None,
                 request_timeout: float = 60.0,
                 on_notification: Callable[[dict], None] | None = None):
        self.exe = exe
        self._api_key = api_key if api_key is not None else _read_stored_api_key()
        self._env_extra = extra_env or {}
        self.request_timeout = request_timeout
        self.on_notification = on_notification
        self._proc: subprocess.Popen | None = None
        self._rx: "queue.Queue[dict]" = queue.Queue()
        self._reader: threading.Thread | None = None
        self._id = 0
        self._lock = threading.Lock()
        self._stderr_tail: list[str] = []
        self.agent_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.auth_methods: list[dict[str, Any]] = []
        self.authenticated = False
        # Agent→client JSON-RPC requests (e.g. session/request_permission,
        # fs/read_text_file). The handler returns a result dict or raises
        # AcpError whose code/message become the response error.
        self.agent_request_handler: Callable[[dict], Any] | None = None

    # ------------------------------------------------------------------ proc
    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        if not Path(self.exe).is_file():
            raise AcpTransportError(f"devin binary not found: {self.exe}")
        env = dict(os.environ)
        env.update(self._env_extra)
        # CREATE_NO_WINDOW: without it Windows allocates `devin acp` a
        # transient console; when that console tears down the process
        # dies with 0xC000013A (CTRL_C). Also stops CMD window flicker
        # on every spawn — the user's reported symptom.
        _flags = 0x08000000 if os.name == "nt" else 0
        self._proc = subprocess.Popen(
            [self.exe, "acp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, text=True,
            creationflags=_flags,
            # ACP traffic is UTF-8 JSON — never the locale codepage; a
            # cp1250 decode of 0x88+ bytes crashes the reader thread.
            encoding="utf-8", errors="replace",
            env=env, cwd=os.path.expanduser("~"))
        self._rx = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "clientCapabilities": {"fs": {"readTextFile": True,
                                          "writeTextFile": True},
                                   "terminal": True},
            "clientInfo": {"name": "realjarvis-devin-bridge", "version": "1.0"}},
            timeout=self.request_timeout)
        self.capabilities = result.get("agentCapabilities", {})
        self.auth_methods = result.get("authMethods", [])
        self.agent_info = result.get("agentInfo", {})

        if not self._api_key:
            raise AcpAuthRequired(
                "No Devin API key available. Set DEVIN_ACP_API_KEY or run "
                "`devin auth login`. Not dispatching.", code=-32000)
        self._request("authenticate", {
            "methodId": "devin-browser",
            "_meta": {"api_key": self._api_key}}, timeout=self.request_timeout)
        self.authenticated = True

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._rx.put(json.loads(line))
            except ValueError:
                pass

    def _drain_stderr(self) -> None:
        try:
            assert self._proc and self._proc.stderr
            for line in self._proc.stderr:
                self._stderr_tail.append(line.rstrip())
                del self._stderr_tail[:-40]
        except Exception:
            pass

    def _request(self, method: str, params: dict | None = None,
                 timeout: float | None = None) -> dict:
        if not self._proc or self._proc.poll() is not None:
            raise AcpTransportError("devin acp process is not running")
        with self._lock:
            self._id += 1
            rid = self._id
        assert self._proc.stdin
        try:
            self._proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "id": rid, "method": method,
                 "params": params or {}}) + "\n")
            self._proc.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            raise AcpTransportError(f"acp stdin write failed: {e}")
        deadline = time.time() + (timeout or self.request_timeout)
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise AcpTransportError(
                    "devin acp exited (code %s): %s" % (
                        self._proc.returncode,
                        " | ".join(self._stderr_tail[-5:])))
            try:
                msg = self._rx.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("id") == rid and "method" not in msg:
                if "error" in msg:
                    err = msg["error"]
                    exc = (AcpAuthRequired if "auth" in str(
                        err.get("message", "")).lower() else AcpError)
                    raise exc(err.get("message", "acp error"),
                              code=err.get("code"), data=err.get("data"))
                return msg.get("result") or {}
            if "method" in msg and "id" in msg:
                self._answer_agent_request(msg)
                continue
            self._dispatch_notification(msg)
        raise AcpTransportError(f"acp request timed out: {method}")

    def _answer_agent_request(self, msg: dict) -> None:
        """Respond to an agent→client request (permission, fs, terminal)."""
        resp: dict[str, Any] = {"jsonrpc": "2.0", "id": msg.get("id")}
        try:
            if self.agent_request_handler is None:
                raise AcpError("method not supported by this host",
                               code=-32601)
            result = self.agent_request_handler(msg)
            resp["result"] = result if result is not None else {}
        except AcpError as e:
            resp["error"] = {"code": e.code or -32603,
                             "message": str(e), "data": e.data}
        except Exception as e:  # noqa: BLE001 — fail closed
            resp["error"] = {"code": -32603, "message": f"host error: {e}"}
        try:
            assert self._proc and self._proc.stdin
            self._proc.stdin.write(json.dumps(resp) + "\n")
            self._proc.stdin.flush()
        except OSError:
            pass

    def _dispatch_notification(self, msg: dict) -> None:
        if "method" not in msg:
            return
        if self.on_notification:
            try:
                self.on_notification(msg)
            except Exception:
                pass

    # ------------------------------------------------------------- sessions
    # Modes the bridge is allowed to select for new sessions.
    # 'bypass'/'dangerous'/'autonomous' are NEVER set — smart is the
    # unattended ceiling; anything it can't clear escalates to us.
    ALLOWED_MODES = {"smart", "accept-edits", "plan", "ask"}

    def session_new(self, cwd: str, model: str | None = None,
                    mode: str | None = "smart",
                    timeout: float | None = None) -> dict:
        if mode and mode not in self.ALLOWED_MODES:
            raise AcpError(
                f"refusing to start session in mode '{mode}' — allowed: "
                f"{sorted(self.ALLOWED_MODES)}", code=-32602)
        params: dict[str, Any] = {"cwd": cwd, "mcpServers": []}
        if model:
            params["model"] = model
        result = self._request("session/new", params,
                               timeout=timeout or self.request_timeout)
        sid = result.get("sessionId", "")
        if mode and sid:
            try:
                self.set_config_option(sid, "mode", mode)
            except AcpError:
                pass
        return result

    def session_load(self, session_id: str, cwd: str,
                     timeout: float | None = None) -> dict:
        return self._request("session/load", {
            "sessionId": session_id, "cwd": cwd, "mcpServers": []},
            timeout=timeout or self.request_timeout)

    def session_list(self, timeout: float | None = None) -> list[dict]:
        result = self._request("session/list", {},
                               timeout=timeout or self.request_timeout)
        return list(result.get("sessions") or [])

    def set_config_option(self, session_id: str, config_id: str,
                          value: str) -> dict:
        return self._request("session/set_config_option", {
            "sessionId": session_id, "configId": config_id, "value": value})

    def session_cancel(self, session_id: str) -> None:
        try:
            self._proc.stdin.write(json.dumps({  # type: ignore[union-attr]
                "jsonrpc": "2.0", "method": "session/cancel",
                "params": {"sessionId": session_id}}) + "\n")
            self._proc.stdin.flush()  # type: ignore[union-attr]
        except OSError:
            pass

    def session_close(self, session_id: str, force: bool = True) -> None:
        try:
            self._request("session/close", {
                "sessionId": session_id,
                "_meta": {"cognition.ai/force": force}}, timeout=10)
        except AcpError:
            pass

    def session_prompt(self, session_id: str, text: str,
                       on_update: Callable[[dict], None] | None = None,
                       timeout: float = 3600.0,
                       collect_updates: bool = True) -> PromptResult:
        """Send a prompt and wait for the terminal ``session/prompt`` result.

        Collects streamed ``session/update`` notifications matching the
        session into a :class:`PromptResult`. A prompt is a *turn* — the
        returned ``stop_reason`` is the honest end signal (``end_turn``,
        ``cancelled``, ``refusal``, ``max_tokens``, …), never assumed.
        """
        chunks: list[str] = []
        thoughts: list[str] = []
        tools: list[dict] = []
        usage: dict[str, Any] = {}
        plan: dict | None = None
        count = [0]

        def _route(msg: dict) -> None:
            params = msg.get("params") or {}
            if params.get("sessionId") != session_id:
                return
            upd = params.get("update") or {}
            kind = upd.get("sessionUpdate")
            if not kind:
                return
            count[0] += 1
            if kind == "agent_message_chunk":
                chunks.append(str((upd.get("content") or {}).get("text", "")))
            elif kind == "agent_thought_chunk":
                thoughts.append(str((upd.get("content") or {}).get("text", "")))
            elif kind == "usage_update":
                usage.update({k: v for k, v in upd.items()
                              if k != "sessionUpdate"})
            elif kind in ("tool_call", "tool_call_update"):
                tools.append(upd)
            elif kind == "plan":
                plan = upd
            if on_update:
                try:
                    on_update(upd)
                except Exception:
                    pass

        prev = self.on_notification
        if collect_updates:
            def combined(msg: dict) -> None:
                _route(msg)
                if prev:
                    prev(msg)
            self.on_notification = combined
        try:
            result = self._request("session/prompt", {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}]}, timeout=timeout)
        finally:
            if collect_updates:
                self.on_notification = prev
        meta = result.get("_meta") or {}
        return PromptResult(
            stop_reason=str(result.get("stopReason", "")),
            text="".join(chunks),
            usage=result.get("usage") or usage,
            thought="".join(thoughts),
            tool_calls=tools, plan=plan,
            user_message_id=str(meta.get("cognition.ai/userMessageId", "")),
            raw_updates=count[0])

    # ---------------------------------------------------------------- misc
    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.poll() is None)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass
        self._proc = None
        self.authenticated = False

    def restart(self) -> None:
        self.stop()
        self.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
