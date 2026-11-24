"""C05: same task generation for Chat and original native route; no real searches."""
import json
import shutil
import unittest
import uuid
from unittest.mock import patch

import task_packet

m = task_packet.heritage


class SharedTaskTest(unittest.TestCase):
    def setUp(self):
        # Use the real original init and prepare with a temporary dev run ID.
        self.run_id = "c05_fixture_" + uuid.uuid4().hex
        self.work = m.RUNS / self.run_id
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        m.original_call(m.original_command("init", self.run_id, theme="Offline task fixture"))
        # Set up synthetic, explicitly offline stage inputs using original digest.
        # No formal receipt or real event/search result is represented.
        import sys
        sys.path.insert(0, str(m.V32 / "tools"))
        from staged_topic import digest
        reality = {"phenomenon": "Fixture", "search_focus": "Coordination",
                   "sources": [{"url": "https://example.org", "kind": "fixture",
                                "supports": "Fixture", "limits": "No actual evidence"}]}
        exchange = {"candidate_question": "How does coordination occur?", "search_focus": "Fixture"}
        plan = {"issue": "Coordination", "why": "Fixture rationale",
                "object_search": "Object", "issue_search": "Issue", "theory_search": "Theory",
                "specialist_journals": []}
        for name, data in (("reality.json", reality), ("explanation_exchange.json", exchange),
                           ("issue_plan.json", plan)):
            m.write(self.work / name, data)
        state = m.state_of(self.run_id)
        state.update(status="initial", reality_sha256=digest(reality),
                     exchange_sha256=digest(exchange), issue_plan_sha256=digest(plan))
        m.write(self.work / "staged_topic.json", state)

    def test_same_initial_packet_and_reference(self):
        chat = m.chat_task(self.run_id, "initial")
        codex = m.codex_task(self.run_id, "initial")
        self.assertEqual(chat["task_packet"], codex["task_packet"])
        self.assertEqual(chat["task_snapshot"], codex["task_snapshot"])
        packet = chat["task_packet"]
        self.assertEqual(packet["quantity_budget"]["target"], chat["target"])
        self.assertEqual(packet["source_scope"]["journals"], chat["journals"])
        self.assertEqual(packet["search_levels"], ["object", "issue", "theory"])
        task_packet.verify_snapshot(chat["task_snapshot"], current_run_id=self.run_id)
        self.assertEqual(m.state_of(self.run_id)["status"], "initial")

    def test_original_native_dispatch_uses_frozen_packet_and_original_cli(self):
        real_call = m.original_call
        calls = []
        def offline_call(cmd, **kwargs):
            if cmd[3] == "initial":
                calls.append(cmd)
                return "offline dispatch fixture"
            return real_call(cmd, **kwargs)
        with patch.object(m, "original_call", side_effect=offline_call):
            result = m.status(self.run_id, progress=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], m.original_command("initial", self.run_id))
        self.assertEqual(result["task_snapshot"], m.codex_task(self.run_id, "initial")["task_snapshot"])

    def test_same_supplemental_packet_binds_previous_evidence(self):
        from staged_topic import digest
        matrix = {"rows": [{"title": "Previously accepted fixture paper"}]}
        theories = []
        comparison = {"fixture_only": True}
        for name, data in (("initial/literature_matrix.json", matrix),
                           ("initial/theories.json", theories),
                           ("event_comparison.json", comparison)):
            m.write(self.work / name, data)
        state = m.state_of(self.run_id)
        state.update(status="supplemental", question="Revised fixture question",
                     initial_sha256=digest(matrix),
                     event_comparison_sha256=digest(comparison))
        m.write(self.work / "staged_topic.json", state)
        chat = m.chat_task(self.run_id, "supplemental")
        codex = m.codex_task(self.run_id, "supplemental")
        self.assertEqual(chat["task_packet"], codex["task_packet"])
        self.assertEqual(chat["task_snapshot"], codex["task_snapshot"])
        self.assertEqual(chat["accepted"], ["Previously accepted fixture paper"])
        paths = {row["path"] for row in chat["task_packet"]["input_files"]}
        self.assertTrue({"initial/literature_matrix.json", "initial/theories.json",
                         "event_comparison.json"} <= paths)
        task_packet.verify_snapshot(chat["task_snapshot"], current_run_id=self.run_id)

    def test_phase_change_and_wrong_phase_rejected(self):
        with self.assertRaisesRegex(ValueError, "not authorized"):
            m.codex_task(self.run_id, "supplemental")
        with self.assertRaisesRegex(ValueError, "not authorized"):
            m.chat_task(self.run_id, "supplemental")


if __name__ == "__main__":
    unittest.main()
