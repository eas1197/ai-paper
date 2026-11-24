"""C20 offline native-log fixtures; never actual CLI execution."""
import json
import unittest
import test_result_bundle_binding as binding
from test_result_bundle_schema import search_action
import codex_receiving


class CodexReceivingTest(unittest.TestCase):
    setUp = binding.ResultBindingTest.setUp
    make_packet = binding.ResultBindingTest.make_packet
    setup_ref = binding.ResultBindingTest.setup_ref
    raw = binding.ResultBindingTest.raw
    save = binding.ResultBindingTest.save
    expected = binding.ResultBindingTest.expected
    fixture = binding.ResultBindingTest.fixture

    def sample(self):
        self.setup_ref()
        bundle = self.fixture("codex_cli")
        p = bundle["provenance"]
        folder = "fixture/attempt_001/"
        base = "/host/offline_fixture/" + folder
        events = [{"type": "thread.started", "thread_id": "fixture-thread"},
                  {"type": "item.completed", "item": {"type": "web_search", "id": "open-1",
                       "action": {"type": "open_page", "url": "https://example.org/abstract"},
                       "results": [{"url": "https://example.org/abstract"}, {"url": "https://example.org/paper"}]}}]
        p.update(events=self.raw(folder+"events.jsonl", ("\n".join(json.dumps(e) for e in events)+"\n").encode()),
                 stderr=self.raw(folder+"stderr.log", b""),
                 prompt=self.raw(folder+"prompt.txt", b"Offline fixture"),
                 schema=self.raw(folder+"schema.json", b"{}"),
                 login=self.raw(folder+"login_diagnostics.json", b'{"chatgpt":true,"exit_code":0,"stdout":"Logged in using ChatGPT","stderr":""}'))
        p["command"] = ["codex", "-a", "never", "--search", "exec", "--ignore-user-config",
                        "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C",
                        base.rstrip("/"), "--json", "--output-schema", base+"schema.json", "-o", base+"response.json", "-"]
        bundle.update(search_actions=[search_action()], execution_status="completed", failure_reasons=[])
        self.rebind(bundle)
        return bundle

    def rebind(self, bundle):
        p = bundle["provenance"]
        record = {"task_snapshot": self.ref, "argv": p["command"],
                  "exit_code": p["exit_code"], "thread_id": p["thread_id"],
                  "files": {key: p.get(key) for key in ("events","response","stderr","prompt","schema","login")}}
        p["command_record"] = self.raw("fixture/attempt_001/invocation.json", json.dumps(record).encode())
        self.save(bundle)

    def receive(self, bundle, independent=True):
        return codex_receiving.audit_codex_records(self.result_path, current_run_id="offline_fixture",
            expected_reference=self.ref, expected_execution=self.expected(bundle) if independent else None)

    def test_c20_native_files_command_and_source_binding(self):
        bundle = self.sample()
        report = self.receive(bundle)
        self.assertEqual(report["native_event_count"], 1)
        self.assertTrue(report["command_record_matched"])
        self.assertTrue(report["native_cli_receipt"])
        self.assertFalse(report["formal_eligible"])
        self.assertEqual(report["codex_source_receipts"][0]["opened_event_ids"], ["open-1"])
        self.assertFalse(self.receive(bundle, independent=False)["native_cli_receipt"])

    def test_c20_unrecorded_command_or_wrong_thread_never_promoted(self):
        bundle = self.sample()
        bundle["provenance"].pop("command_record")
        self.save(bundle)
        self.assertFalse(self.receive(bundle)["native_cli_receipt"])
        bundle = self.sample_again(bundle)
        bundle["provenance"]["thread_id"] = "other-thread"
        self.rebind(bundle)
        with self.assertRaisesRegex(ValueError, "thread.started"):
            self.receive(bundle)

    def sample_again(self, bundle):
        self.rebind(bundle)
        return bundle

    def test_c20_reject_non_native_command_and_unmatched_source(self):
        bundle = self.sample()
        bundle["provenance"]["command"][7] = "danger-full-access"
        self.rebind(bundle)
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.receive(bundle)
        bundle["provenance"]["command"][7] = "read-only"
        bundle["sources"][0]["abstract_url"] = "https://example.org/unmatched"
        self.rebind(bundle)
        self.assertFalse(self.receive(bundle)["native_cli_receipt"])


if __name__ == "__main__":
    unittest.main()
