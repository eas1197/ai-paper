"""C19 offline fixtures: matching saved text is not proof of real Chat execution."""
import json
import unittest
import test_result_bundle_binding as binding
from test_result_bundle_schema import search_action
import chat_receiving


class ChatReceivingTest(unittest.TestCase):
    setUp = binding.ResultBindingTest.setUp
    make_packet = binding.ResultBindingTest.make_packet
    setup_ref = binding.ResultBindingTest.setup_ref
    raw = binding.ResultBindingTest.raw
    save = binding.ResultBindingTest.save
    expected = binding.ResultBindingTest.expected
    fixture = binding.ResultBindingTest.fixture

    def sample(self):
        self.setup_ref()
        bundle = self.fixture()
        action = search_action()
        bundle["search_actions"] = [action]
        bundle.update(execution_status="completed", failure_reasons=[])
        ref = self.raw("fixture/chat_visible.txt", b"Offline fixture\nhttps://example.org/abstract\n")
        bundle["provenance"]["record_refs"] = [ref]
        self.save(bundle)
        observed = [{"action_id": "open-1", "action_type": "open_page", "record_ref": ref,
                     "line_start": 2, "line_end": 2, "query": None,
                     "urls": ["https://example.org/abstract"]}]
        return bundle, observed

    def receive(self, bundle, observed=None, independent=True):
        return chat_receiving.audit_chat_records(self.result_path, current_run_id="offline_fixture",
            expected_reference=self.ref, expected_execution=self.expected(bundle) if independent else None,
            observed_actions=observed)

    def test_c19_original_record_and_open_match_not_formal(self):
        bundle, observed = self.sample()
        report = self.receive(bundle, observed)
        self.assertEqual(report["matched_action_ids"], ["open-1"])
        self.assertEqual(report["chat_source_receipts"][0]["opened_action_ids"], ["open-1"])
        self.assertFalse(report["host_authenticated"])
        self.assertFalse(report["native_cli_receipt"])
        self.assertFalse(report["formal_eligible"])

    def test_c19_missing_independent_records_remain_pending(self):
        bundle, observed = self.sample()
        for report in (self.receive(bundle), self.receive(bundle, observed, independent=False)):
            self.assertEqual(report["acceptance_status"], "pending_candidate")
            self.assertFalse(report["matched_action_ids"])

    def test_c19_mismatched_record_location_or_url_rejected(self):
        bundle, observed = self.sample()
        observed[0]["line_start"] = 1
        observed[0]["line_end"] = 1
        with self.assertRaisesRegex(ValueError, "URL not found"):
            self.receive(bundle, observed)
        observed[0]["line_end"] = 2
        observed[0]["urls"] = ["https://example.org/other"]
        with self.assertRaisesRegex(ValueError, "URL not found"):
            self.receive(bundle, observed)

    def test_c19_never_convert_native_cli_event_stream(self):
        bundle, observed = self.sample()
        ref = self.raw("fixture/events.jsonl", b'{"type":"thread.started","thread_id":"fixture"}\n')
        bundle["provenance"]["record_refs"] = [ref]
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "not a Chat web record"):
            self.receive(bundle)
        native = self.fixture("codex_cli")
        with self.assertRaisesRegex(ValueError, "Only chat_native_web"):
            self.receive(native)


if __name__ == "__main__":
    unittest.main()
