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

    def test_p01_04_partial_independent_action_index_remains_pending(self):
        bundle, observed = self.sample()
        row = bundle["sources"][0]
        row["literature_stages"]["abstract_read_status"] = "read"
        row["paraphrase"] = "Fixture summary " * 7
        ref = self.raw("fixture/chat_visible.txt",
            ("https://example.org/abstract\n" + row["abstract_locator"] + "\n"
             + row["excerpt"] + "\nfixture query\nhttps://example.org/abstract\n").encode())
        bundle["provenance"]["record_refs"] = [ref]
        observed[0].update(record_ref=ref, line_start=1, line_end=3)
        action = dict(bundle["search_actions"][0], action_id="search-2",
                      action_type="search", query="fixture query", original_url=None)
        bundle["search_actions"].append(action)
        row["action_ids"].append("search-2")
        self.save(bundle)
        report = self.receive(bundle, observed)
        self.assertEqual(report["unmatched_action_ids"], ["search-2"])
        self.assertEqual(report["acceptance_status"], "pending_candidate")
        self.assertEqual(report["chat_record_status"], "pending_original_chat_records")
        self.assertFalse(report["formal_eligible"])
        observed.append({"action_id": "search-2", "action_type": "search",
            "record_ref": ref, "line_start": 4, "line_end": 5,
            "query": "fixture query", "urls": ["https://example.org/abstract"]})
        report = self.receive(bundle, observed)
        self.assertEqual(report["unmatched_action_ids"], [])
        self.assertEqual(report["chat_record_status"], "matched_visible_records_pending_authentication")
        self.assertFalse(report["host_authenticated"])
        self.assertFalse(report["native_cli_receipt"])
        self.assertFalse(report["formal_eligible"])

    def test_p01_04_original_record_hash_applies_to_exact_read_bytes(self):
        self.setup_ref()
        from unittest.mock import patch
        from pathlib import Path
        import hashlib
        ref = self.raw("fixture/chat_visible.txt", b"original record")
        with patch.object(Path, "read_bytes", return_value=b"changed record"):
            with self.assertRaisesRegex(ValueError, "Chat original record changed"):
                chat_receiving._raw_record(self.root / "offline_fixture", ref)
        self.assertEqual(ref["sha256"], hashlib.sha256(b"original record").hexdigest())
        self.assertEqual(chat_receiving._raw_record(self.root / "offline_fixture", ref),
                         ["original record"])

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

    def test_c22_missing_locator_or_excerpt_stays_pending(self):
        bundle, observed = self.sample()
        for key in ("abstract_locator", "excerpt"):
            original = bundle["sources"][0][key]
            bundle["sources"][0][key] = None
            self.save(bundle)
            report = self.receive(bundle, observed)
            self.assertEqual(report["acceptance_status"], "pending_candidate")
            self.assertFalse(report["chat_source_receipts"][0]["abstract_matched_action_ids"])
            self.assertFalse(report["formal_eligible"])
            bundle["sources"][0][key] = original

    def test_c22_search_hit_is_not_open_or_abstract_read(self):
        bundle, observed = self.sample()
        action = bundle["search_actions"][0]
        action.update(action_type="search", query="fixture query", original_url=None)
        ref = self.raw("fixture/chat_visible.txt", b"fixture query\nhttps://example.org/abstract\n")
        bundle["provenance"]["record_refs"] = [ref]
        observed[0].update(action_type="search", query="fixture query", record_ref=ref,
                           line_start=1, line_end=2)
        self.save(bundle)
        report = self.receive(bundle, observed)
        receipt = report["chat_source_receipts"][0]
        self.assertEqual(receipt["discovery_action_ids"], ["open-1"])
        self.assertFalse(receipt["opened_action_ids"])
        self.assertEqual(report["acceptance_status"], "pending_candidate")

    def test_c22_abstract_must_be_visible_at_independently_observed_open_location(self):
        bundle, observed = self.sample()
        row = bundle["sources"][0]
        row["literature_stages"]["abstract_read_status"] = "read"
        row["paraphrase"] = "Fixture summary " * 7
        self.save(bundle)
        report = self.receive(bundle, observed)
        self.assertIn("abstract_locator_or_excerpt_not_visible_in_open_record",
                      report["chat_source_receipts"][0]["gaps"])
        ref = self.raw("fixture/chat_visible.txt",
            ("https://example.org/abstract\n"+row["abstract_locator"]+"\n"+row["excerpt"]+"\n").encode())
        bundle["provenance"]["record_refs"] = [ref]
        observed[0].update(record_ref=ref, line_start=1, line_end=3)
        self.save(bundle)
        report = self.receive(bundle, observed)
        self.assertEqual(report["chat_source_receipts"][0]["abstract_matched_action_ids"], ["open-1"])
        self.assertFalse(report["host_authenticated"])
        self.assertFalse(report["formal_eligible"])
        self.assertEqual(self.receive(bundle, observed, independent=False)["acceptance_status"], "pending_candidate")

    def test_p0504_visible_action_accounting_is_not_platform_usage(self):
        bundle, observed = self.sample()
        report = self.receive(bundle, observed)["chat_action_observation"]
        self.assertEqual(report["matched_counts"], {"search": 0, "open_page": 1, "find_in_page": 0})
        self.assertEqual(report["matched_success_records"], observed)
        for key in ("actual_host_action_total", "actual_model_calls", "actual_tokens",
                    "actual_fee", "formal_budget_charge"):
            self.assertIsNone(report[key])
        self.assertFalse(report["host_authenticated"])
        pending = self.receive(bundle, observed, independent=False)["chat_action_observation"]
        self.assertEqual(pending["matched_success_records"], [])
        self.assertEqual(pending["unmatched_claimed_action_ids"], ["open-1"])
        self.assertIsNone(pending["actual_host_action_total"])

    def test_p0504_failed_search_without_results_preserved_without_source_receipt(self):
        bundle, observed = self.sample()
        bundle.update(execution_status="failed", failure_reasons=["Timed out"], sources=[],
            execution_issues=[{"code":"timeout", "scope":"run", "target_id":None,
                               "detail":"Timed out", "original_status":"failed"}])
        bundle["search_actions"][0].update(action_type="search", query="fixture query",
            original_url=None, source_ids=[], failure_reason="Timed out")
        ref = self.raw("fixture/chat_visible.txt", b"fixture query\nTimed out\n")
        bundle["provenance"]["record_refs"] = [ref]
        observed[0].update(action_type="search", query="fixture query", urls=[],
                           record_ref=ref, line_start=1, line_end=2)
        self.save(bundle)
        report = self.receive(bundle, observed)
        obs = report["chat_action_observation"]
        self.assertEqual(report["acceptance_status"], "rejected")
        self.assertEqual(obs["matched_counts"]["search"], 1)
        self.assertEqual(obs["matched_failure_records"][0]["failure_reason"], "Timed out")
        self.assertEqual(obs["matched_success_records"], [])
        self.assertEqual(report["chat_source_receipts"], [])
        self.assertIsNone(obs["formal_budget_charge"])
        bundle["search_actions"][0]["failure_reason"] = "Fabricated reason"
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "failure is absent"):
            self.receive(bundle, observed)


if __name__ == "__main__":
    unittest.main()
