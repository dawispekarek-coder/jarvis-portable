"""P0 security tests — chat tool handler hardening.

Guarantees under test:
  * terminal/create runs ONLY the exact shape
        <python> -m DevinBridge.jarvis_tools run <whitelisted tool>
        [--json '<object>']
    executed with the fixed sys.executable + MODULE_ROOT cwd.
  * caller-supplied cwd/env/args can never influence the subprocess.
  * fs paths are contained by real ancestry (resolve+relative_to),
    including junction/symlink escapes.
  * every other request is denied and recorded with a diagnostic.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from DevinBridge import jarvis_tools
from DevinBridge.acp_client import AcpError
from DevinBridge.chat import (CHAT_HOME, MODULE_ROOT, ChatToolHandler,
                              _Terminals)


def _mk_handler(tmp: Path) -> ChatToolHandler:
    class _C:  # minimal coord stub
        root = tmp
        _chat_sid = ""

        def approved_fingerprints(self):
            return set()

        def dashboard_link(self, rid, appr):
            return f"http://127.0.0.1:1/?t={rid}"

    class _N:
        def approval_required(self, *a, **k):
            return {"sent": False, "outcome": "test"}

    from DevinBridge.approvals import ApprovalManager
    h = ChatToolHandler(_C(), _N(), ApprovalManager(tmp))
    return h


class TestTerminalAllowlist(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chatsec-"))
        self.terms = _Terminals(self.tmp)

    def _create(self, cmd: str, **extra):
        params = {"command": cmd}
        params.update(extra)
        return self.terms.handle("terminal/create", params)

    # ---------- accepted shapes ----------
    def test_accepts_exact_shape(self):
        tid = self._create(
            "python -m DevinBridge.jarvis_tools run get_time"
        )["terminalId"]
        self.assertTrue(tid)

    def test_accepts_py_and_json_object(self):
        argv, why = self.terms._allowed(
            {"command": "py -m DevinBridge.jarvis_tools run get_time "
                        "--json '{\"k\": 1}'"})
        self.assertIsNotNone(argv, why)

    def test_accepts_sys_executable(self):
        import sys
        argv, _ = self.terms._allowed(
            {"command": f'"{sys.executable}" -m DevinBridge.jarvis_tools'
                        " run get_time"})
        self.assertIsNotNone(argv)

    def test_fixed_interpreter_and_module_root_cwd(self):
        """Whatever the caller passes, we exec sys.executable from
        MODULE_ROOT — the cwd that makes `python -m DevinBridge...`
        importable (the 'wrong module root' bug)."""
        res = self._create("python -m DevinBridge.jarvis_tools run get_time",
                           cwd="C:\\Windows\\System32")
        t = self.terms.terms[res["terminalId"]]
        self.assertEqual(t["cwd"], str(MODULE_ROOT))
        import sys
        self.assertEqual(t["proc"].args[0], sys.executable)

    # ---------- denied shapes ----------
    def _denied(self, cmd: str, **extra) -> str:
        with self.assertRaises(AcpError) as cm:
            self._create(cmd, **extra)
        return str(cm.exception)

    def test_denies_bare_shell(self):
        self._denied("cmd /c dir")

    def test_denies_python_inline(self):
        self._denied('python -c "import os; os.system(\'calc\')"')

    def test_denies_lookalike_module(self):
        self._denied("python -m DevinBridge.jarvis_tools_evil run x")
        self._denied("python -m DevinBridge.jarvis_tools.run x")

    def test_denies_non_run_subcommand(self):
        self._denied("python -m DevinBridge.jarvis_tools list")
        self._denied("python -m DevinBridge.jarvis_tools exec get_time")

    def test_denies_unknown_tool(self):
        self._denied("python -m DevinBridge.jarvis_tools run rm_rf")
        self._denied("python -m DevinBridge.jarvis_tools run jarvis_status;")

    def test_denies_shell_trailers(self):
        self._denied("python -m DevinBridge.jarvis_tools run get_time && calc")
        self._denied("python -m DevinBridge.jarvis_tools run get_time | more")
        self._denied("python -m DevinBridge.jarvis_tools run get_time; calc")

    def test_denies_wrapper_shells(self):
        self._denied('bash -c "python -m DevinBridge.jarvis_tools run get_time"')
        self._denied("powershell -Command python -m DevinBridge.jarvis_tools run get_time")
        self._denied("cmd.exe /c python -m DevinBridge.jarvis_tools run get_time")

    def test_denies_bad_json_arg(self):
        self._denied("python -m DevinBridge.jarvis_tools run get_time --json notjson")
        self._denied("python -m DevinBridge.jarvis_tools run get_time --json '[1,2]'")
        self._denied("python -m DevinBridge.jarvis_tools run get_time --verbose")

    def test_denies_args_env_overrides(self):
        self._denied("python -m DevinBridge.jarvis_tools run get_time",
                     args=["-x"])
        self._denied("python -m DevinBridge.jarvis_tools run get_time",
                     env={"PATH": "C:\\evil"})

    def test_denials_are_recorded(self):
        self._denied("whoami")
        self.assertTrue(self.terms.denials)
        self.assertIn("python", self.terms.denials[-1]["reason"]
                      + self.terms.denials[-1]["reason"])

    # ---------- happy-path execution ----------
    def test_tool_actually_runs(self):
        res = self._create("python -m DevinBridge.jarvis_tools run get_time")
        out = self.terms.handle("terminal/output",
                                {"terminalId": res["terminalId"]})
        self.assertEqual(out["exitStatus"]["exitCode"], 0)
        self.assertRegex(out["output"].strip(), r"^\d{2}:\d{2}:\d{2}$")

    # ---------- bounded lifecycle (live bug: 40/51 failed) ----------
    def test_25_sequential_calls_no_exhaustion(self):
        """The real-world failure: sequential allowed commands must NOT
        exhaust slots — finished processes are reclaimed."""
        tids = []
        for i in range(25):
            r = self._create(
                "python -m DevinBridge.jarvis_tools run get_time")
            tids.append(r["terminalId"])
            self.terms.handle("terminal/output",
                              {"terminalId": r["terminalId"]})
        self.assertEqual(len(set(tids)), 25)
        # every proc finished; entries may linger only until next create
        self.assertLessEqual(self.terms._live(), 0)

    def test_parallel_cap_counts_live_only(self):
        """8 LIVE procs at once -> 9th denied; after one exits, next
        create succeeds. Concurrency, not total history, is bounded."""
        import subprocess as _sp
        import sys as _sys
        import uuid as _uuid
        # fake long-running entries
        for i in range(8):
            tid = _uuid.uuid4().hex[:16]
            self.terms.terms[tid] = {
                "proc": _sp.Popen(
                    [_sys.executable, "-c", "import time;time.sleep(30)"],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    creationflags=0x08000000),
                "buf": None, "argv": "sleep", "cwd": str(self.tmp)}
        try:
            with self.assertRaises(AcpError) as ctx:
                self._create(
                    "python -m DevinBridge.jarvis_tools run get_time")
            self.assertIn("concurrent", str(ctx.exception))
            # kill one -> slot frees, create succeeds
            first = next(iter(self.terms.terms.values()))
            first["proc"].kill()
            first["proc"].wait()
            first["buf"] = ""          # agent already consumed output
            r = self._create(
                "python -m DevinBridge.jarvis_tools run get_time")
            self.assertTrue(r["terminalId"])
        finally:
            for t in self.terms.terms.values():
                if t["proc"].poll() is None:
                    t["proc"].kill()

    def test_release_idempotent(self):
        r = self._create("python -m DevinBridge.jarvis_tools run get_time")
        tid = r["terminalId"]
        self.terms.handle("terminal/release", {"terminalId": tid})
        # second release of a gone id is a no-op, not an error
        self.assertEqual(
            self.terms.handle("terminal/release", {"terminalId": tid}),
            {})
        self.assertEqual(
            self.terms.handle("terminal/kill", {"terminalId": tid}), {})

    def test_blocked_shell_does_not_consume_slot(self):
        for _ in range(12):
            with self.assertRaises(AcpError):
                self._create("cmd /c echo hi")
            with self.assertRaises(AcpError):
                self._create("python -c 'print(1)'")
        self.assertEqual(len(self.terms.terms), 0)
        self.assertGreaterEqual(len(self.terms.denials), 12)


class TestPathContainment(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chatfs-"))
        self.h = _mk_handler(self.tmp)
        self.home = self.h.home
        self.home.mkdir(parents=True, exist_ok=True)

    def _denied(self, path: str):
        with self.assertRaises(AcpError):
            self.h({"method": "fs/read_text_file",
                    "params": {"path": path}})

    def test_inside_home_ok(self):
        r = self.h({"method": "fs/write_text_file",
                    "params": {"path": "notes/a.txt", "content": "hi"}})
        self.assertEqual(r, {})
        self.assertTrue((self.home / "notes" / "a.txt").is_file())

    def test_dotdot_escape_denied(self):
        self._denied("../escape.txt")
        self._denied("subdir/../../escape.txt")
        self._denied(str(self.home.parent / "escape.txt"))

    def test_absolute_outside_denied(self):
        self._denied("C:/Windows/win.ini")

    def test_prefix_lookalike_denied(self):
        """chat_home2 / chat_home.evil must not pass ancestry checks."""
        sib = self.home.parent / (self.home.name + "2")
        sib.mkdir(exist_ok=True)
        (sib / "x.txt").write_text("x")
        self._denied(str(sib / "x.txt"))

    def test_junction_escape_denied(self):
        """A junction inside home pointing outside must resolve out."""
        outside = self.tmp / "outside"
        outside.mkdir(exist_ok=True)
        (outside / "secret.txt").write_text("s3cret")
        link = self.home / "linkdir"
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            self.skipTest("cannot create junction: "
                          f"{(r.stderr or r.stdout or '').strip()}")
        self._denied("linkdir/secret.txt")

    def test_write_outside_denied(self):
        with self.assertRaises(AcpError):
            self.h({"method": "fs/write_text_file",
                    "params": {"path": "../evil.txt", "content": "x"}})
        self.assertFalse((self.home.parent / "evil.txt").exists())


class TestToolSurface(unittest.TestCase):
    def test_status_tool_is_whitelisted(self):
        """'Jaký je stav Jarvise?' must be servable by ONE whitelisted
        call — jarvis_status stays in TOOLS."""
        self.assertIn("jarvis_status", jarvis_tools.TOOLS)
        self.assertIn("get_time", jarvis_tools.TOOLS)
        # no mutating tools may ever appear unreviewed
        for name in jarvis_tools.TOOLS:
            self.assertNotRegex(name, r"(delete|remove|write|exec|shell|send)")

    def test_status_returns_json(self):
        out = jarvis_tools.main(["run", "jarvis_status"])
        self.assertEqual(out, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
