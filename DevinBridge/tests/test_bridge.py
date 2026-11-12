"""Hermetic tests for the Devin bridge — no live Devin needed.

Run:  python -m unittest discover -s tests -v
A live-ACP smoke path exists only in test_acp_live.py (opt-in env flag).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from DevinBridge import acp_client  # noqa: E402
from DevinBridge.coordinator import Coordinator  # noqa: E402
from DevinBridge import bridge_store  # noqa: E402

FAKE = str(ROOT / "tests" / "fake_acp.py")


def make_fake_exe(tmp: Path) -> str:
    """Create a fake 'devin' executable wrapper running fake_acp.py."""
    bat = tmp / "fake_devin.bat"
    py = sys.executable
    bat.write_text(f'@echo off\n"{py}" "{FAKE}" %*\n', encoding="utf-8")
    return str(bat)


class FakeClient(acp_client.DevinAcpClient):
    def __init__(self, exe):
        super().__init__(exe=exe, api_key="test-key")


def spawn_fake(exe) -> FakeClient:
    c = FakeClient(exe)
    c.start()
    return c


class TestAcpClient(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bridgetest_"))
        self.exe = make_fake_exe(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_handshake_auth_session_prompt(self):
        c = spawn_fake(self.exe)
        try:
            self.assertTrue(c.authenticated)
            sess = c.session_new(str(self.tmp), model="swe-2-high")
            sid = sess["sessionId"]
            res = c.session_prompt(sid, "say hi")
            self.assertEqual(res.stop_reason, "end_turn")
            self.assertEqual(res.text, "MOCK_OK")
            self.assertEqual(res.usage["totalTokens"], 100)
            lst = c.session_list()
            self.assertTrue(any(s["sessionId"] == sid for s in lst))
            loaded = c.session_load(sid, str(self.tmp))
            self.assertIn("modes", loaded)
        finally:
            c.stop()

    def test_set_config_option_invalid_model(self):
        c = spawn_fake(self.exe)
        try:
            sess = c.session_new(str(self.tmp))
            with self.assertRaises(acp_client.AcpError):
                c.set_config_option(sess["sessionId"], "model", "swe-2-max")
        finally:
            c.stop()

    def test_auth_failure(self):
        c = acp_client.DevinAcpClient(exe=self.exe, api_key="")
        with self.assertRaises(acp_client.AcpAuthRequired):
            c.start()
        c.stop()


class TestCoordinator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="coordtest_"))
        self.bridge_root = self.tmp / "bridge"
        self.queue_root = self.tmp / "queue"
        self.worktree = self.tmp / "wt"
        self.worktree.mkdir(parents=True)
        self.queue_root.mkdir()
        self.exe = make_fake_exe(self.tmp)
        (self.queue_root / "queue_state.json").write_text(
            json.dumps({"tasks": {}, "activeTaskId": "",
                        "pendingDispatch": None, "lastResult": ""}),
            encoding="utf-8")
        subprocess.run(["git", "init"], cwd=self.worktree,
                       capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"],
                       cwd=self.worktree, capture_output=True)
        import os as _os
        _os.environ["FAKE_ACP_SESSIONS"] = str(self.tmp / "fake_sess.json")

    def tearDown(self):
        import os as _os
        _os.environ.pop("FAKE_ACP_SESSIONS", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def coord(self, mode="safe") -> Coordinator:
        c = Coordinator(
            root=self.bridge_root, queue_root=self.queue_root,
            client_factory=lambda: FakeClient(self.exe),
            model="swe-2-high", mode=mode)
        # Run prompt workers in-process on THIS coordinator+fake client —
        # the production path spawns a detached real worker which could
        # never see the fake ACP server.
        import threading as _th
        from DevinBridge import prompt_worker as _pw

        def _spawn(tid, followup=""):
            t = _th.Thread(target=_pw.run_with, args=(c, tid, followup),
                           daemon=True)
            t.start()
            return __import__("os").getpid()
        c._spawn_worker = _spawn
        return c

    def _add(self, c, tid="T900_TEST", acc=None, approved=True):
        return c.add_task(tid, "test task",
                          f"do work CREATE_FILE:proof.txt:hello",
                          str(self.worktree),
                          acceptance=acc or
                          [{"type": "file_exists", "path": "proof.txt"}],
                          approved=approved)

    def test_add_approve_dispatch_verify_complete(self):
        c = self.coord()
        r = self._add(c)
        self.assertTrue(r["added"])
        # safe mode: manual dispatch requires approval — granted in _add
        d = c.dispatch("T900_TEST")
        self.assertTrue(d["dispatched"], d)
        # prompt thread is async — wait for VERIFYING→terminal
        for _ in range(80):
            t = c.get_task("T900_TEST")
            if t["status"] in ("COMPLETE", "FAILED", "NEEDS_REVIEW"):
                break
            time.sleep(0.1)
        t = c.get_task("T900_TEST")
        self.assertEqual(t["status"], "COMPLETE",
                         json.dumps(t, indent=1)[:1500])
        self.assertTrue((self.worktree / "proof.txt").is_file())
        # session id is attached by the worker once session/new returns
        self.assertTrue(t["session_id"].startswith("fake-session"))

    def test_dispatch_idempotent(self):
        c = self.coord()
        self._add(c)
        d1 = c.dispatch("T900_TEST")
        self.assertTrue(d1["dispatched"])
        d2 = c.dispatch("T900_TEST")
        self.assertFalse(d2["dispatched"])
        self.assertIn(d2.get("reason", ""), ("already RUNNING",
                                             "already DISPATCHED",
                                             "already VERIFYING",
                                             "already COMPLETE"))

    def test_duplicate_add(self):
        c = self.coord()
        self.assertTrue(self._add(c)["added"])
        self.assertFalse(self._add(c)["added"])

    def test_unapproved_not_dispatched(self):
        c = self.coord()
        self._add(c, approved=False)
        d = c.dispatch("T900_TEST")
        self.assertFalse(d["dispatched"])

    def test_safe_mode_no_autodispatch(self):
        c = self.coord(mode="safe")
        self._add(c)
        res = c.tick()
        self.assertTrue(any("safe mode" in h or "suppressed" in a
                            for h in res["holds"] for a in res["actions"])
                        or not res["actions"]
                        or res["holds"])
        self.assertEqual(c.get_task("T900_TEST")["status"], "READY")

    def test_retry_backoff_then_fail(self):
        c = self.coord()
        c.max_retries = 1
        self._add(c, acc=[{"type": "file_exists", "path": "never.txt"}])
        d = c.dispatch("T900_TEST")
        self.assertTrue(d["dispatched"])
        for _ in range(80):
            t = c.get_task("T900_TEST")
            if t["status"] in ("FAILED", "NEEDS_REVIEW", "READY", "COMPLETE"):
                break
            time.sleep(0.1)
        t = c.get_task("T900_TEST")
        # attempts==1 == max_retries → FAILED (no infinite retry)
        self.assertEqual(t["status"], "FAILED", json.dumps(t)[:800])
        self.assertEqual(t["attempts"], 1)

    def test_persistence_across_restart(self):
        c = self.coord()
        self._add(c)
        c2 = self.coord()  # fresh instance, same root
        t = c2.get_task("T900_TEST")
        self.assertTrue(t)
        self.assertEqual(t["status"], "PENDING")

    def test_pause_resume(self):
        c = self.coord()
        c.pause("test")
        self.assertTrue(c.paused)
        self.assertIn("bridge paused (PAUSED.flag)", c.global_holds())
        c.resume()
        self.assertFalse(c.paused)

    def test_autonomous_requires_flag(self):
        c = self.coord()
        with self.assertRaises(PermissionError):
            c.set_mode("autonomous")
        (self.bridge_root / "AUTONOMOUS_ENABLED.flag").mkdir(
            parents=True, exist_ok=True) if False else None
        Path(self.bridge_root).mkdir(parents=True, exist_ok=True)
        (self.bridge_root / "AUTONOMOUS_ENABLED.flag").write_text("on")
        c.set_mode("autonomous")
        self.assertEqual(c.mode, "autonomous")

    def test_legacy_hold_blocks_legacy_worktree(self):
        # pendingDispatch in legacy queue_state blocks dispatch into the
        # legacy repo worktree.
        (self.queue_root / "queue_state.json").write_text(json.dumps({
            "tasks": {}, "activeTaskId": "",
            "pendingDispatch": {"taskId": "T148_X", "head": "abc",
                                "promptSent": False},
            "lastResult": "HOLD_UNCONFIRMED_DISPATCH"}), encoding="utf-8")
        c = self.coord()
        c.add_task("T901_L", "legacy", "x",
                   r"C:\Users\Dawis\Saved Games\ForeverRoute-db70338",
                   approved=True)
        d = c.dispatch("T901_L")
        self.assertFalse(d["dispatched"])
        self.assertIn("pendingDispatch", d["reason"])

    def test_worktree_conflict_guard(self):
        c = self.coord()
        self._add(c, tid="T910_A")
        self._add(c, tid="T911_B")
        c.dispatch("T910_A")
        d = c.dispatch("T911_B")
        self.assertFalse(d["dispatched"])
        self.assertIn("worktree busy", d["reason"])


class TestStore(unittest.TestCase):
    def test_atomic_json_and_jsonl(self):
        tmp = Path(tempfile.mkdtemp(prefix="storetest_"))
        try:
            p = tmp / "a.json"
            bridge_store.atomic_write_json(p, {"x": 1})
            self.assertEqual(bridge_store.read_json(p), {"x": 1})
            bridge_store.append_jsonl(tmp / "e.jsonl", {"k": "v"})
            bridge_store.append_jsonl(tmp / "e.jsonl", {"k": "v2"})
            self.assertEqual(len(bridge_store.read_jsonl(tmp / "e.jsonl")), 2)
            k = bridge_store.dispatch_key("T1", "sha", "head")
            self.assertEqual(len(k), 24)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
