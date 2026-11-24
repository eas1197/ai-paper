"""C25 handoff harness, explicitly offline tests, not real execution evidence."""
import json
import unittest
from unittest.mock import patch

import c25_acceptance as c25
import test_shared_task_packet as shared
import test_original_literature_gate as original
import task_packet


class PreparePairTest(unittest.TestCase):
    setUp = shared.SharedTaskTest.setUp

    def test_prepare_same_frozen_pair_without_search_and_no_overwrite(self):
        result = c25.prepare_pair(self.run_id, "initial", "offline_fixture")
        manifest = c25.heritage.read(self.work / result["pair"]["path"])
        self.assertFalse(manifest["search_executed"])
        chat = c25._read_ref(self.work, manifest["chat_task"])
        native = c25._read_ref(self.work, manifest["codex_task"])
        self.assertEqual(chat["task_packet"], native["task_packet"])
        self.assertEqual(chat["task_snapshot"], native["task_snapshot"])
        self.assertEqual(c25.heritage.state_of(self.run_id)["status"], "initial")
        with self.assertRaisesRegex(ValueError, "new in-run directory"):
            c25.prepare_pair(self.run_id, "initial", "offline_fixture")

    def test_preflight_missing_cli_does_not_check_login(self):
        c25.original_literature_gate._original()
        with patch("codex_literature.cli_executable", side_effect=RuntimeError("CLI unavailable")), \
             patch("codex_literature.login_probe") as probe:
            result = c25.preflight()
        self.assertEqual(result["status"], "blocked_missing_authorized_codex_environment")
        self.assertFalse(result["login_checked"])
        probe.assert_not_called()


class CheckPairTest(unittest.TestCase):
    setUp = original.OriginalLiteratureGateTest.setUp
    make_packet = original.OriginalLiteratureGateTest.make_packet
    setup_ref = original.OriginalLiteratureGateTest.setup_ref
    raw = original.OriginalLiteratureGateTest.raw
    save = original.OriginalLiteratureGateTest.save
    expected = original.OriginalLiteratureGateTest.expected
    fixture = original.OriginalLiteratureGateTest.fixture
    sample = original.OriginalLiteratureGateTest.sample

    def pair_fixture(self):
        native = self.sample()
        snapshot = task_packet.verify_snapshot(self.ref, current_run_id="offline_fixture")
        chat_task = self.raw("fixture/chat_task.json", json.dumps(
            {"task_snapshot": self.ref, "task_packet": snapshot["packet"],
             "source_mode": "chat_native_web"}).encode())
        native_task = self.raw("fixture/codex_task.json", json.dumps(
            {"task_snapshot": self.ref, "task_packet": snapshot["packet"]}).encode())
        manifest = {"schema_version":1,"kind":"c25_dual_executor_handoff",
                    "task_snapshot":self.ref,"chat_task":chat_task,"codex_task":native_task,
                    "search_executed":False}
        pair = self.raw("fixture/pair.json", json.dumps(manifest).encode())
        native_binding = self.expected(native)
        self.raw("fixture/native_result.json", (self.work / self.result_path).read_bytes())
        self.raw("fixture/native_binding.json", json.dumps(native_binding).encode())
        chat = self.fixture()
        chat_binding = self.expected(chat)
        self.raw("fixture/chat_result.json", (self.work / self.result_path).read_bytes())
        self.raw("fixture/chat_binding.json", json.dumps(chat_binding).encode())
        selection = {
            "chat_native_web":{"result_path":"fixture/chat_result.json",
                               "execution_binding":"fixture/chat_binding.json"},
            "codex_cli":{"result_path":"fixture/native_result.json",
                         "execution_binding":"fixture/native_binding.json"}}
        return pair["path"], selection

    def test_both_original_receivers_read_but_unobserved_chat_stays_pending(self):
        pair, selection = self.pair_fixture()
        result = c25.audit_pair("offline_fixture", pair, selection)
        self.assertTrue(result["same_receiver_read_both"])
        self.assertEqual(result["status"], "pending_missing_dual_execution_evidence")
        self.assertFalse(result["c25_verified"])
        self.assertFalse(result["formal_eligible"])
        self.assertEqual(result["reports"]["codex_cli"]["original_verified_rows"], 1)
        self.assertEqual(result["reports"]["chat_native_web"]["acceptance_status"], "pending_candidate")

    def test_swapped_executor_or_tampered_handoff_rejected(self):
        pair, selection = self.pair_fixture()
        selection["chat_native_web"], selection["codex_cli"] = selection["codex_cli"], selection["chat_native_web"]
        with self.assertRaisesRegex(ValueError, "wrong executor"):
            c25.audit_pair("offline_fixture", pair, selection)
        self.raw("fixture/chat_task.json", b"{}")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            c25.audit_pair("offline_fixture", pair, selection)


if __name__ == "__main__":
    unittest.main()
