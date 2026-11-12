"""Safe regression coverage for RealJarvis V2 on-demand tool training."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tool_learning as t


class ToolTrainingTests(unittest.TestCase):
    def test_exact_czech_command_is_executable_intent(self):
        for value in (
            "Nauč se pracovat se vším co máš k dispozici",
            "Jarvisi, nauč se pracovat se vším, co máš k dispozici",
            "Prostuduj si všechny své nástroje",
            "Nauč se svoje nástroje", "/naucse"
        ):
            with self.subTest(value=value):
                self.assertEqual(t.training_intent(value), "run")
        self.assertEqual(t.training_intent("Co ses naučil používat za nástroje?"), "status")

    def test_other_requests_are_not_training(self):
        for value in ("Nauč mě pracovat s internetem", "Co je učení?",
                      "Nauč se programovat Lua", "Vyhledej novinky",
                      "Jak se učí jazykový model?", "Zajímá mě TTS"):
            with self.subTest(value=value):
                self.assertIsNone(t.training_intent(value))

    def test_discovery_is_real_and_unknown_tools_not_executed(self):
        items = t.discover(({"name": "web_search_public"}, {"name": "unknown_shell_write"},
                            {"name": "../danger"}))
        names = [x["id"] for x in items]
        self.assertIn("memory", names)
        self.assertIn("tts", names)
        self.assertIn("advertised:web_search_public", names)
        self.assertIn("advertised:unknown_shell_write", names)
        self.assertNotIn("advertised:../danger", names)
        self.assertEqual(len(set(names)), len(names))

    def test_explicit_train_persists_evidence_and_status(self):
        with tempfile.TemporaryDirectory(prefix="v2_learning_tests_") as directory:
            db = Path(directory) / "skills.sqlite"
            signals = []
            overrides = {k: (lambda key=k: (
                "VERIFIED", {"fixture": True, "id_ok": bool(key)}, "synthetic unit test"))
                for k in t.GROUPS}
            with patch.object(t, "_probe_skill", side_effect=AssertionError("override must prevent real execution")):
                result = t.train_all(
                    advertised_tools=({"name": "external_tool"},),
                    db_path=db, report=lambda e: signals.append(e),
                    probe_overrides=overrides)
            self.assertEqual(result["status"], "COMPLETED")
            self.assertEqual(result["checked"], len(t.GROUPS) + 1)
            self.assertEqual(len(signals), result["checked"])
            self.assertEqual(result["counts"]["UNTESTED"], 1)
            state = t.current(db)
            self.assertEqual(state["status"], "COMPLETED")
            self.assertEqual(state["discovered"], result["checked"])
            self.assertIn("git", t.GROUPS["code"][0].casefold() + " git")
            self.assertTrue(any(s["id"] == "code" for s in state["skills"]))
            self.assertEqual(next(s for s in state["skills"] if s["id"] ==
                                 "advertised:external_tool")["status"], "UNTESTED")
            context = t.skill_context(db)
            self.assertIn("code=VERIFIED", context)
            self.assertNotIn("synthetic unit test", context)
            self.assertFalse(db.with_suffix(".running.lock").exists())

    def test_stale_source_demotes_result(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "skills.sqlite"
            overrides = {k: (lambda: ("VERIFIED", {"ok": True}, "test")) for k in t.GROUPS}
            t.train_all(db_path=db, probe_overrides=overrides)
            with patch.object(t, "_source_digest", return_value="CHANGED"):
                state = t.current(db)
            self.assertIn("STALE", [s["status"] for s in state["skills"]])
            self.assertNotIn("code=VERIFIED", t.skill_context(db) if False else "")

    def test_concurrent_lock_will_not_overwrite_record(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "skills.sqlite"
            lock = db.with_suffix(".running.lock")
            lock.write_text("another process", encoding="utf-8")
            result = t.train_all(db_path=db)
            self.assertEqual(result["status"], "BUSY")
            self.assertEqual(lock.read_text(encoding="utf-8"), "another process")

    def test_probe_failure_is_honest_and_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "skills.sqlite"
            def broken():
                raise ValueError("deliberate fixture exception")
            overrides = {k: (lambda: ("READY", {"ok": True}, "unit")) for k in t.GROUPS}
            overrides["tts"] = broken
            result = t.train_all(db_path=db, probe_overrides=overrides)
            self.assertEqual(result["status"], "COMPLETED")
            self.assertEqual(result["counts"]["FAILED"], 1)
            failed = next(s for s in t.current(db)["skills"] if s["id"] == "tts")
            self.assertEqual(failed["evidence"]["error_type"], "ValueError")

    def test_memory_fixture_read_write_without_owner_db(self):
        result, proof, note = t._probe_skill("memory")
        self.assertEqual(result, "VERIFIED")
        self.assertTrue(proof["write_read_duplicate_fixture_passed"])
        self.assertFalse(proof["real_user_notes_modified"])

    def test_browser_is_a_safe_simulation_not_window_open(self):
        with patch("webbrowser.open", side_effect=AssertionError("must never open a real browser")):
            status, evidence, _ = t._probe_skill("browser")
        self.assertEqual(status, "READY")
        self.assertFalse(evidence["real_browser_opened"])

    def test_external_cloud_not_triggered(self):
        result, info, _ = t._probe_skill("external_ai")
        self.assertEqual(result, "NEEDS_APPROVAL")
        self.assertFalse(info["external_request_sent"])


if __name__ == "__main__":
    unittest.main()
