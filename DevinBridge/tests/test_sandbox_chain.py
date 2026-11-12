"""P4 controlled proof — deterministic dependent-task chain in an
isolated git sandbox, negative permission scenario, planner provenance,
crash-recovery dedup and protected-worktree holds. All hermetic:
fake ACP, mock ntfy, temp dirs."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from DevinBridge.acp_client import DevinAcpClient  # noqa: E402
from DevinBridge.approvals import ApprovalManager  # noqa: E402
from DevinBridge.coordinator import Coordinator  # noqa: E402
from DevinBridge import planner, prompt_worker  # noqa: E402
from test_approvals import (MockNtfy, fake_exe, git_init,  # noqa: E402
                            wait_for)


def make_coord(root: Path, **kw):
    exe = fake_exe(root)
    c = Coordinator(
        root=root / "bridge", queue_root=root, model="swe-2-high",
        client_factory=lambda: DevinAcpClient(exe=exe, api_key="test"),
        **kw)

    def fake_spawn(task_id, followup=""):
        th = threading.Thread(target=prompt_worker.run_with,
                              args=(c, task_id, followup), daemon=True)
        th.start()
        return os.getpid()
    c._spawn_worker = fake_spawn
    return c


class TestDependentChain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chain_"))
        self.wt = self.tmp / "repo"
        self.wt.mkdir()
        git_init(self.wt)
        self.ntfy = ThreadingHTTPServer(("127.0.0.1", 0), MockNtfy)
        threading.Thread(target=self.ntfy.serve_forever,
                         daemon=True).start()
        MockNtfy.received.clear()
        os.environ["DEVIN_BRIDGE_NTFY_BASE"] = \
            f"http://127.0.0.1:{self.ntfy.server_port}"
        os.environ["FAKE_ACP_SESSIONS"] = \
            str(self.tmp / "fake_sessions.json")
        self.c = make_coord(self.tmp)

    def tearDown(self):
        self.ntfy.shutdown()
        os.environ.pop("DEVIN_BRIDGE_NTFY_BASE", None)
        os.environ.pop("FAKE_ACP_SESSIONS", None)
        if self.c._client:
            self.c._client.stop()

    def test_two_task_chain_and_recovery(self):
        c = self.c
        # --- task A ---------------------------------------------------
        c.add_task("P-A", "step A", "CREATE_FILE:step_a.txt:ALPHA DONE",
                   str(self.wt), approved=True, scope="production",
                   owner="human", reason="sandbox chain step 1",
                   acceptance=[{"type": "file_exists",
                                "path": "step_a.txt"}],
                   declared_followups=[{
                       "title": "step B", "prompt":
                       "CREATE_FILE:step_b.txt:BETA after A",
                       "acceptance": [{"type": "file_contains",
                                       "path": "step_a.txt",
                                       "pattern": "ALPHA"}]}])
        # --- task B depends on A -------------------------------------
        c.add_task("P-B", "step B", "CREATE_FILE:step_b.txt:BETA after A",
                   str(self.wt), approved=True, scope="production",
                   depends_on=["P-A"],
                   acceptance=[{"type": "file_exists",
                                "path": "step_b.txt"}])
        # B must not be eligible while A is incomplete
        cand, why = c.next_eligible()
        self.assertEqual(cand["id"], "P-A")
        self.assertTrue(c.dispatch("P-A")["dispatched"])
        self.assertTrue(wait_for(
            lambda: c.get_task("P-A")["status"] == "COMPLETE", 20))
        # now B became eligible via dependency resolution
        cand, why = c.next_eligible()
        self.assertEqual(cand["id"], "P-B")
        self.assertTrue(c.dispatch("P-B")["dispatched"])
        self.assertTrue(wait_for(
            lambda: c.get_task("P-B")["status"] == "COMPLETE", 20))
        self.assertEqual((self.wt / "step_b.txt").read_text(),
                         "BETA after A")

        # --- planner: A's declared followup becomes a PROPOSAL, not a task
        res = planner.propose(c)
        self.assertTrue(res["created"], res)
        prop = res["created"][0]
        self.assertEqual(prop["source"], "declared_followup")
        open_p = planner.list_proposals(c)
        self.assertEqual(open_p[0]["requires_human_approval"], True)
        # second run dedupes — no double proposal for the same prompt
        res2 = planner.propose(c)
        self.assertFalse(res2["created"])
        # promote → real task, approved=False (planner can't self-approve)
        pr = planner.promote(c, prop["proposal_id"])
        self.assertTrue(pr["ok"])
        t = c.get_task(pr["task_id"])
        self.assertFalse(t["approved"])
        self.assertEqual(t["generated_by"], "planner")
        self.assertIn("acceptance_passed", t["evidence_refs"])

        # --- crash/recovery: fresh coordinator on the same root must not
        # redispatch COMPLETE work or resurrect the chain
        c2 = make_coord(self.tmp)
        out = c2.tick(autonomous_dispatch=False)
        self.assertFalse([a for a in out["actions"]
                          if "auto-dispatch P-A" in a or
                          "auto-dispatch P-B" in a])
        self.assertEqual(c2.get_task("P-A")["status"], "COMPLETE")
        self.assertEqual(c2.get_task("P-B")["status"], "COMPLETE")
        d = c2.dispatch("P-A")  # COMPLETE → refused, not re-sent
        self.assertFalse(d["dispatched"])

    def test_negative_permission_blocks_and_holds(self):
        c = self.c
        # PERM:write triggers a genuine host permission request; policy
        # ASKs → approval record → NEEDS_APPROVAL; task must NOT complete.
        c.add_task("P-NEG", "out-of-scope action",
                   "PERM:execute:run elevated installer outside "
                   "workspace then CREATE_FILE:nope.txt:x",
                   str(self.wt), approved=True, scope="production")
        self.assertTrue(c.dispatch("P-NEG")["dispatched"])
        mgr = ApprovalManager(c.root)
        self.assertTrue(wait_for(lambda: mgr.pending(), 20))
        self.assertTrue(wait_for(
            lambda: c.get_task("P-NEG")["status"] == "NEEDS_APPROVAL", 20))
        self.assertFalse((self.wt / "nope.txt").exists())
        # reject → BLOCKED, terminal — no retry, no file
        req = mgr.pending()[0]
        mgr.decide(req["request_id"], approved=False, decided_by="test")
        c.deny("P-NEG", note="test reject")
        self.assertTrue(wait_for(
            lambda: c.get_task("P-NEG")["status"] == "BLOCKED", 20))
        self.assertFalse((self.wt / "nope.txt").exists())

    def test_protected_worktree_and_legacy_holds(self):
        gui = self.tmp / "gui_repo"
        gui.mkdir()
        git_init(gui)
        c = make_coord(self.tmp, protected_worktrees=[str(gui)])
        c.add_task("P-GUI", "would touch GUI repo",
                   "CREATE_FILE:x.txt:x", str(gui), approved=True,
                   scope="production")
        r = c.dispatch("P-GUI")
        self.assertFalse(r["dispatched"])
        self.assertIn("protected worktree", r["reason"])
        # legacy T81 flag → global hold blocks auto dispatch
        (self.tmp / "T81_EXTERNAL_ACTIVE.flag").write_text("hold")
        holds = c.global_holds()
        self.assertTrue(any("T81" in h for h in holds))

    def test_guarded_autonomy_requires_flag(self):
        """AUTONOMOUS only fires while the human-created flag exists —
        removing it must suppress the very next tick."""
        c = self.c
        c.add_task("P-AUTO", "auto work", "CREATE_FILE:auto.txt:OK",
                   str(self.wt), approved=True, scope="production",
                   acceptance=[{"type": "file_exists", "path": "auto.txt"}])
        # no flag → set_mode refuses outright
        with self.assertRaises(PermissionError):
            c.set_mode("autonomous")
        # create the human artifact → mode switch succeeds → tick works
        c.autonomous_flag.write_text("enabled by test")
        try:
            c.set_mode("autonomous")
            out = c.tick(autonomous_dispatch=True)
            self.assertTrue(any("auto-dispatch P-AUTO" in a
                                for a in out["actions"]), out)
            self.assertTrue(wait_for(
                lambda: c.get_task("P-AUTO")["status"] == "COMPLETE", 25))
        finally:
            c.autonomous_flag.unlink(missing_ok=True)
            st = c._load(); st["mode"] = "safe"; c._save(st)
        # flag gone → holds suppress even if mode file still said so
        out2 = c.tick(autonomous_dispatch=True)
        self.assertTrue(any("suppressed" in a or "no dispatch" in a
                            for a in out2["actions"]), out2)

    def test_cdp_handoff_loop_and_limits(self):
        """3-step CDP cycle inside an owner program file: proposal →
        handoff dispatch → verify → next proposal; budget + scope + stop
        all enforced."""
        import json as _j
        from DevinBridge import cdp
        c = self.c
        # owner program: 2-task budget, this worktree only, analyze only
        prog_dir = c.root / "autonomy_scope"
        prog_dir.mkdir(parents=True, exist_ok=True)
        (prog_dir / "CDP_PROGRAM.json").write_text(_j.dumps({
            "program_id": "TEST-PROG", "worktrees": [str(self.wt)],
            "kinds": ["analyze"], "max_tasks": 2,
            "expires_epoch": __import__("time").time() + 3600}))
        # two in-program proposals (priority order: LOW wins)
        for i, pr in ((1, 10), (2, 20)):
            cdp.new_issue_proposal(
                c, "analyze", f"step {i}",
                f"CREATE_FILE:step{i}.txt:OK{i}", str(self.wt),
                f"issue {i}", ["test:sandbox"],
                acceptance=[{"type": "file_exists",
                             "path": f"step{i}.txt"}], priority=pr)
        # out-of-program proposal — never dispatched by handoff
        cdp.new_issue_proposal(c, "analyze", "outside wt",
                               "CREATE_FILE:out.txt:x", str(self.tmp),
                               "outside", ["test:sandbox"], priority=1)
        # step 1
        h1 = cdp.handoff_tick(c)
        self.assertTrue(h1["handoff"], h1)
        self.assertTrue(wait_for(
            lambda: c.get_task(h1["task_id"])["status"] == "COMPLETE",
            25))
        self.assertTrue((self.wt / "step1.txt").exists())
        # evidence collected + verified
        ev = cdp.collect(c, h1["task_id"])
        self.assertTrue(ev["evidence"]["verified"])
        self.assertIn("step1.txt", ev["evidence"]["produced_files"])
        # step 2 — same worktree free again
        h2 = cdp.handoff_tick(c)
        self.assertTrue(h2["handoff"], h2)
        self.assertTrue(wait_for(
            lambda: c.get_task(h2["task_id"])["status"] == "COMPLETE",
            25))
        # budget exhausted — out-of-scope + remaining never run
        h3 = cdp.handoff_tick(c)
        self.assertFalse(h3["handoff"])
        self.assertIn("budget", h3["reason"])
        self.assertFalse((self.tmp / "out.txt").exists())
        # expired program → fail closed
        (prog_dir / "CDP_PROGRAM.json").write_text(_j.dumps({
            "program_id": "TEST-PROG", "worktrees": [str(self.wt)],
            "kinds": ["analyze"], "max_tasks": 9,
            "expires_epoch": __import__("time").time() - 1}))
        self.assertFalse(cdp.handoff_tick(c)["handoff"])

    def test_failure_recovery_verified_and_unblocks(self):
        """FR-REPAIR-01-shaped failure: unittest acceptance fails 2/4
        -> RCA 'wrong_implementation' -> ONE bounded corrective child
        -> ORIGINAL acceptance re-runs and passes -> parent becomes
        VERIFIED_RECOVERED (never rewritten to COMPLETE) -> dependent
        unblocks -> restart creates no duplicate recovery; a failed
        corrective ESCALATES (max 2 attempts); unauthed worktree waits."""
        import json as _j
        import subprocess as _sp
        from DevinBridge import recovery
        c = make_coord(self.tmp,
                       authorized_worktrees=[str(self.wt)])
        adir = c.root / "autonomy_scope"
        adir.mkdir(parents=True, exist_ok=True)
        import time as _t
        (adir / "TEST_AUTHORIZATION.json").write_text(_j.dumps({
            "worktree": str(self.wt), "kinds": ["repair-small"],
            "allowed_task_ids": ["FR-REPAIR-DEMO-01", "FR-FAIL-DEMO-02"],
            "allowed_paths": ["tools/", "tests/", "docs/"],
            "attempts_per_task": 1, "max_tokens": 50000,
            "expires_epoch": _t.time() + 3600}))
        buggy = ("def classify_qid(qid):\n"
                 "    return 'POLESTAR_HISTORICAL_REFERENCE_ONLY'\n")
        fixed = ("def classify_qid(qid):\n"
                 "    return ('P2_STRUCTURAL_WITH_LEADS_INFERENCE'\n"
                 "            if qid in (10, 11)\n"
                 "            else 'POLESTAR_HISTORICAL_REFERENCE_ONLY')\n")
        (self.wt / "tools").mkdir(exist_ok=True)
        (self.wt / "tools" / "route_nav_evidence_audit.py") \
            .write_text(buggy)
        (self.wt / "tools" / "__init__.py").write_text("")
        (self.wt / "tests").mkdir(exist_ok=True)
        (self.wt / "tests" / "test_nav.py").write_text(
            "import sys, unittest\nsys.path.insert(0, 'tools')\n"
            "import route_nav_evidence_audit as r\n"
            "class T(unittest.TestCase):\n"
            " def test_q10(self): self.assertEqual(r.classify_qid(10),"
            " 'P2_STRUCTURAL_WITH_LEADS_INFERENCE')\n"
            " def test_q11(self): self.assertEqual(r.classify_qid(11),"
            " 'P2_STRUCTURAL_WITH_LEADS_INFERENCE')\n"
            " def test_q99(self): self.assertEqual(r.classify_qid(99),"
            " 'POLESTAR_HISTORICAL_REFERENCE_ONLY')\n"
            " def test_q42(self): self.assertEqual(r.classify_qid(42),"
            " 'POLESTAR_HISTORICAL_REFERENCE_ONLY')\n")
        pre = _sp.run([sys.executable, "-m", "unittest", "discover",
                       "-s", "tests", "-p", "test_nav.py"],
                      cwd=str(self.wt), capture_output=True, text=True)
        self.assertEqual(pre.returncode, 1)   # 2 real failures
        acc = [{"type": "test", "runner": "unittest",
                "args": ["discover", "-s", "tests", "-p", "test_nav.py"]}]
        c.add_task("FR-REPAIR-DEMO-01", "nav audit",
                   "CREATE_FILE:note.txt:analysis done",
                   str(self.wt), approved=True, scope="production",
                   owner="human", acceptance=acc, max_attempts=1)
        c._mutate("FR-REPAIR-DEMO-01", lambda x: x.__setitem__(
            "repair_directive",
            "CREATE_FILE:tools/route_nav_evidence_audit.py:" + fixed))
        c.add_task("FR-NEXT-DEMO", "next", "CREATE_FILE:after.txt:ok",
                   str(self.wt), approved=True, scope="production",
                   owner="human", depends_on=["FR-REPAIR-DEMO-01"],
                   acceptance=[{"type": "file_exists",
                                "path": "after.txt"}])
        d = c.dispatch("FR-REPAIR-DEMO-01")
        self.assertTrue(d["dispatched"], d)
        self.assertTrue(wait_for(
            lambda: c.get_task("FR-REPAIR-DEMO-01")["status"]
            == "FAILED", 30))
        # dependent stays blocked while dep is FAILED
        self.assertFalse(c.dispatch("FR-NEXT-DEMO")["dispatched"])
        r1 = recovery.tick(c)
        self.assertTrue(any("recovery" in a for a in r1["acted"]), r1)
        child = c.get_task("FR-REPAIR-DEMO-01")["recovery"]["child_id"]
        self.assertTrue(wait_for(
            lambda: c.get_task(child)["status"] == "COMPLETE", 30))
        # original acceptance re-ran green -> supersession, not rewrite
        self.assertTrue(wait_for(
            lambda: c.get_task("FR-REPAIR-DEMO-01")["status"]
            == "VERIFIED_RECOVERED", 10))
        hist = [h["to"] for h in
                c.get_task("FR-REPAIR-DEMO-01")["history"]]
        self.assertIn("FAILED", hist)     # immutable failure evidence
        self.assertIn("VERIFIED_RECOVERED", hist)
        # dependent unblocks and completes
        self.assertTrue(c.dispatch("FR-NEXT-DEMO")["dispatched"])
        self.assertTrue(wait_for(
            lambda: c.get_task("FR-NEXT-DEMO")["status"] == "COMPLETE",
            30))
        # RCA persisted, readable for chat/dashboard
        st = recovery._load(c.root / recovery.STATE_FILE)
        self.assertTrue(any(v.get("category")
                            == "wrong_implementation"
                            for v in st["recoveries"].values()), st)
        # restart: no duplicate recovery spawn
        c2 = make_coord(self.tmp,
                        authorized_worktrees=[str(self.wt)])
        r2 = recovery.tick(c2)
        self.assertFalse(any("FR-REPAIR-DEMO-01 ->" in a
                             for a in r2["acted"]), r2)
        # --- negative: failed corrective -> ESCALATED, no 3rd try ----
        (self.wt / "tools" / "route_nav_evidence_audit.py") \
            .write_text(buggy)
        c2.add_task("FR-FAIL-DEMO-02", "nav audit 2",
                    "CREATE_FILE:n2.txt:x", str(self.wt),
                    approved=True, scope="production", owner="human",
                    acceptance=acc, max_attempts=1)
        d = c2.dispatch("FR-FAIL-DEMO-02")
        self.assertTrue(d["dispatched"], d)
        self.assertTrue(wait_for(
            lambda: c2.get_task("FR-FAIL-DEMO-02")["status"]
            == "FAILED", 30))
        r = recovery.tick(c2)   # child spawned but no directive -> fails
        self.assertTrue(any("FR-FAIL-DEMO-02" in a for a in r["acted"]),
                        r)
        ch1 = c2.get_task("FR-FAIL-DEMO-02")["recovery"]["child_id"]
        self.assertTrue(wait_for(
            lambda: c2.get_task(ch1)["status"] == "FAILED", 30))
        # second (final) attempt — cooldown 0 so the next tick dispatches
        recovery.RECOVERY_COOLDOWN_S = 0
        try:
            recovery.tick(c2)          # schedules attempt 2
            recovery.tick(c2)          # dispatches attempt 2
            ch2 = c2.get_task(
                "FR-FAIL-DEMO-02")["recovery"]["child_id"]
            self.assertNotEqual(ch1, ch2)
            self.assertTrue(wait_for(
                lambda: c2.get_task(ch2)["status"] == "FAILED", 30))
            recovery.tick(c2)          # cap reached -> ESCALATED
        finally:
            recovery.RECOVERY_COOLDOWN_S = 120.0
        rec2 = c2.get_task("FR-FAIL-DEMO-02")["recovery"]
        self.assertEqual(rec2["state"], "ESCALATED")
        self.assertEqual(rec2["attempts"], 2)
        # no further children ever
        again = recovery.maybe_spawn_recovery(c2, "FR-FAIL-DEMO-02")
        self.assertFalse(again.get("spawned"))
        # --- negative: unauthorized worktree -> WAITING_HUMAN --------
        c3 = make_coord(self.tmp)   # no authorized_worktrees/auth file
        c3.add_task("FR-FAIL-DEMO-03", "nav audit 3",
                    "CREATE_FILE:n3.txt:x", str(self.wt),
                    approved=True, scope="production", owner="human",
                    acceptance=acc, max_attempts=1)
        c3._mutate("FR-FAIL-DEMO-03",
                   lambda x: x.__setitem__("status", "FAILED"))
        r3 = recovery.maybe_spawn_recovery(c3, "FR-FAIL-DEMO-03")
        self.assertTrue(r3.get("waiting_human"), r3)

    def test_durable_goal_lifecycle(self):
        """Goal stays OPEN despite child COMPLETE; stages spawn in order;
        no-grant stages queue WAITING_APPROVAL; human gates never
        auto-dispatch; restart produces no duplicates."""
        import json as _j, time as _t
        from DevinBridge import goals
        c = make_coord(self.tmp, authorized_worktrees=[str(self.wt)])
        adir = c.root / "autonomy_scope"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "GOAL_AUTHORIZATION.json").write_text(_j.dumps({
            "worktree": str(self.wt), "kinds": ["analyze"],
            "allowed_task_ids": ["GOAL-T-*"], "attempts_per_task": 1,
            "max_tokens": 5000, "expires_epoch": _t.time() + 3600}))
        goals.add_goal(c.root, "GOAL-T", "test goal", str(self.wt),
            contract=[{"type": "file_exists", "path": "done.flag"}],
            stages=[
                {"title": "s1", "kind": "analyze",
                 "prompt": "CREATE_FILE:s1.txt:one",
                 "acceptance": [{"type": "file_exists",
                                 "path": "s1.txt"}]},
                {"title": "s2", "kind": "analyze",
                 "prompt": "CREATE_FILE:s2.txt:two",
                 "acceptance": [{"type": "file_exists",
                                 "path": "s2.txt"}]},
                {"title": "human validate", "kind": "analyze",
                 "human_gate": True, "prompt": "manual QA",
                 "needs_evidence": "in-game screenshot"}],
            provenance="test", evidence_request="game QA")
        r = goals.tick(c)                       # stage 1 inside grant
        self.assertTrue(any("dispatched GOAL-T-S01" in a
                            for a in r["acted"]), r)
        self.assertTrue(wait_for(
            lambda: c.get_task("GOAL-T-S01")["status"] == "COMPLETE",
            30))
        g = goals.summary(c.root)[0]
        self.assertEqual(g["state"], "OPEN")    # child done != goal done
        r = goals.tick(c)                       # stage 2 spawns
        self.assertTrue(any("GOAL-T-S02" in a for a in r["acted"]), r)
        self.assertTrue(wait_for(
            lambda: c.get_task("GOAL-T-S02")["status"] == "COMPLETE",
            30))
        r = goals.tick(c)                       # stage 3 = human gate
        t3 = c.get_task("GOAL-T-S03")
        self.assertFalse(t3.get("approved"))
        self.assertTrue(t3.get("human_gate"))
        self.assertIn("screenshot", t3.get("waiting_approval", ""))
        self.assertFalse(c.dispatch("GOAL-T-S03")["dispatched"])
        # restart: same stable ids — zero duplicates
        c2 = make_coord(self.tmp,
                        authorized_worktrees=[str(self.wt)])
        n_before = len(c2._load()["tasks"])
        goals.tick(c2)
        self.assertEqual(len(c2._load()["tasks"]), n_before)
        # goal still truthfully OPEN — contract file never written
        g = goals.summary(c2.root)[0]
        self.assertEqual(g["state"], "OPEN")
        self.assertFalse(g["contract_ok"])

    def test_old_audit_grant_blocks_recovery(self):
        """The FR audit authorization grants ONLY FR-SCOPE-* audits —
        it must NEVER authorize a repair recovery. Every grant field is
        enforced: parent ids, kinds, allowed_paths, expiry, budget."""
        import json as _j, time as _t
        from DevinBridge import recovery
        c = make_coord(self.tmp, authorized_worktrees=[str(self.wt)])
        adir = c.root / "autonomy_scope"
        adir.mkdir(parents=True, exist_ok=True)
        # exact shape of the OLD audit grant
        (adir / "FR_SCOPED_AUTONOMY_AUTHORIZATION.json").write_text(
            _j.dumps({"worktree": str(self.wt), "kinds": ["analyze"],
                      "allowed_task_ids": ["FR-SCOPE-20261110-01",
                                           "FR-SCOPE-20261110-02",
                                           "FR-SCOPE-20261110-03"],
                      "attempts_per_task": 1, "max_tokens": 1000,
                      "allowed_paths": ["docs/"],
                      "expires_epoch": _t.time() + 3600}))
        c.add_task("FR-REPAIR-OLD-01", "repair", "x", str(self.wt),
                   approved=True, scope="production", owner="human")
        def _fail(x):
            x["status"] = "FAILED"
            x["evidence"] = {"checks": [{
                "check": "test unittest discover -s tests",
                "ok": False,
                "tail": "AssertionError: 'A' != 'B'"}]}
        c._mutate("FR-REPAIR-OLD-01", _fail)
        r = recovery.maybe_spawn_recovery(c, "FR-REPAIR-OLD-01")
        self.assertTrue(r.get("waiting_human"), r)
        self.assertIn("grant rejected", r.get("reason", ""))
        # grant check itself: parent id absent -> reject even with
        # kinds+paths present
        auth = {"worktree": str(self.wt), "kinds": ["repair-small"],
                "allowed_task_ids": ["FR-SCOPE-20261110-01"],
                "allowed_paths": ["tools/"], "attempts_per_task": 1,
                "max_tokens": 100, "expires_epoch": _t.time() + 3600}
        ok, why = recovery.check_grant(
            auth, {"id": "FR-REPAIR-OLD-01"}, {"paths": ["tools/a.py"]})
        self.assertFalse(ok); self.assertIn("allowed_task_ids", why)
        ok, why = recovery.check_grant(
            auth, {"id": "FR-SCOPE-20261110-01"},
            {"paths": ["tools/a.py", "src/evil.py"]})
        self.assertFalse(ok); self.assertIn("paths outside", why)
        auth2 = dict(auth, expires_epoch=_t.time() - 1)
        ok, why = recovery.check_grant(
            auth2, {"id": "FR-SCOPE-20261110-01"},
            {"paths": ["tools/a.py"]})
        self.assertFalse(ok); self.assertIn("expired", why)
        # no allowed_paths at all -> fail closed
        ok, why = recovery.check_grant(
            dict(auth, allowed_paths=[]),
            {"id": "FR-SCOPE-20261110-01"}, {"paths": ["tools/a.py"]})
        self.assertFalse(ok); self.assertIn("allowed_paths", why)

    def test_cdp_closed_loop_discovery(self):
        """3 injected REAL test failures -> Jarvis discovers issues by
        itself -> synthesizes distinct scoped tasks -> handoff dispatches
        -> verifies -> infers next. No declared_followups, no seeded ids.
        Then: dedup on rerun, stale snapshot -> STOP, missing source ->
        nothing."""
        import json as _j, os as _os, time as _t
        from DevinBridge import cdp, cdp_loop
        c = self.c
        # fixture evidence: real test-results file inside the worktree
        results = {"tests": [
            {"name": "wire_order_sec14", "ok": False,
             "error": "pickup before prereq turnin", "fix_file": "fix1.txt",
             "rerun": "CREATE_FILE:fix1.txt:RESOLVED"},
            {"name": "coverage_56_60", "ok": False,
             "error": "no route rows for 58-60", "fix_file": "fix2.txt",
             "rerun": "CREATE_FILE:fix2.txt:RESOLVED"},
            {"name": "endpoint_continuity", "ok": False,
             "error": "zone transition missing endpoint",
             "fix_file": "fix3.txt",
             "rerun": "CREATE_FILE:fix3.txt:RESOLVED"},
            {"name": "sanity_ok", "ok": True}]}
        (self.wt / "test_results.json").write_text(_j.dumps(results))
        prog_dir = c.root / "autonomy_scope"
        prog_dir.mkdir(parents=True, exist_ok=True)
        (prog_dir / "CDP_PROGRAM.json").write_text(_j.dumps({
            "program_id": "LOOP", "worktrees": [str(self.wt)],
            "kinds": ["analyze", "repair-small"], "max_tasks": 3,
            "expires_epoch": _t.time() + 3600}))
        srcs = [{"type": "test_results", "path": "test_results.json"}]
        # --- cycle 1: discover 3 issues, dispatch first
        s1 = cdp_loop.loop_tick(c, str(self.wt), srcs)
        self.assertEqual(s1["issues"], 3)              # sanity_ok skipped
        self.assertEqual(len(s1["created"]), 3)
        self.assertTrue(s1["handoff"]["handoff"], s1)
        t1 = s1["handoff"]["task_id"]
        self.assertTrue(wait_for(
            lambda: c.get_task(t1)["status"] == "COMPLETE", 25))
        # --- cycle 2: no declared_followups needed — next inferred task
        s2 = cdp_loop.loop_tick(c, str(self.wt), srcs)
        self.assertEqual(s2["created"], [])            # all deduped
        self.assertTrue(s2["handoff"]["handoff"], s2)
        t2 = s2["handoff"]["task_id"]
        self.assertNotEqual(t1, t2)
        self.assertTrue(wait_for(
            lambda: c.get_task(t2)["status"] == "COMPLETE", 25))
        # --- cycle 3: third task runs (budget=3)
        s3 = cdp_loop.loop_tick(c, str(self.wt), srcs)
        if s3["handoff"].get("handoff"):
            self.assertTrue(wait_for(
                lambda: c.get_task(s3["handoff"]["task_id"])["status"]
                == "COMPLETE", 25))
            s3 = cdp_loop.loop_tick(c, str(self.wt), srcs)
        # budget exhausted -> WAITING_HUMAN/STOP, never a 4th dispatch
        self.assertFalse(s3["handoff"]["handoff"])
        self.assertIn(s3["state"], ("WAITING_HUMAN", "STOP"))
        # --- stale snapshot -> generates nothing
        old = _t.time() - 3 * 24 * 3600
        _os.utime(self.wt / "test_results.json", (old, old))
        s4 = cdp_loop.loop_tick(c, str(self.wt), srcs)
        self.assertEqual(s4["issues"], 0)
        self.assertEqual(s4["created"], [])
        self.assertEqual(s4["sources"][0]["reason"],
                         "stale — evidence too old")
        # --- missing source -> nothing
        s5 = cdp_loop.loop_tick(
            c, str(self.wt), [{"type": "test_results",
                               "path": "nonexistent.json"}])
        self.assertEqual(s5["issues"], 0)

    def test_test_scope_never_eligible(self):
        c = self.c
        c.add_task("T900_SMOKE", "synthetic", "CREATE_FILE:s.txt:s",
                   str(self.wt), approved=True)
        self.assertEqual(c.get_task("T900_SMOKE")["scope"], "test")
        cand, why = c.next_eligible()
        self.assertIsNone(cand)
        self.assertIn("synthetic", why)


if __name__ == "__main__":
    unittest.main(verbosity=2)
