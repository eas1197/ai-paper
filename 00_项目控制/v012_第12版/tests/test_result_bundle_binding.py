"""C15: independently selected current task and real file hashes, offline only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import ValidationError

import test_task_packet_ownership as ownership
import test_task_packet_snapshot as snapshots
from test_result_bundle_schema import result, source
import task_packet
import result_bundle


class ResultBindingTest(unittest.TestCase):
    setUp = ownership.TaskOwnershipTest.setUp
    make_packet = snapshots.SnapshotTest.make_packet

    def setup_ref(self):
        self.work = self.root / "offline_fixture"
        self.ref = task_packet.freeze_packet(self.make_packet(), current_run_id="offline_fixture")
        self.result_path = "fixture/result.json"

    def raw(self, relative, content):
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}

    def save(self, bundle):
        self.raw(self.result_path, json.dumps(bundle, ensure_ascii=False).encode("utf-8"))

    def expected(self, bundle):
        # Synthetic receiver-owned fixture, never a claim of actual execution.
        return {"task_snapshot": deepcopy(self.ref), "executor": bundle["executor"],
                "provenance": deepcopy(bundle["provenance"]),
                "result_sha256": task_packet.heritage.sha(self.work / self.result_path)}

    def audit(self, expected=None, reference=None):
        return result_bundle.audit_result_bundle(self.result_path,
            current_run_id="offline_fixture", expected_reference=reference or self.ref,
            expected_execution=expected)

    def fixture(self, kind="chat_native_web"):
        bundle = dict(result(kind), task_snapshot=deepcopy(self.ref), sources=[source()])
        p = bundle["provenance"]
        p["missing_fields"] = []
        if kind == "chat_native_web":
            p["record_refs"] = [self.raw("fixture/chat_record.txt", b"synthetic export only")]
            p["citation_refs"] = ["fixture-citation"]
        elif kind == "manual":
            p.update(submitter="fixture_role", submitted_at="2026-11-24T00:00:00Z",
                     original_files=[self.raw("fixture/manual.txt", b"synthetic original")])
        else:
            p.update(command=["codex", "exec"], thread_id="fixture-thread", exit_code=0,
                     events=self.raw("fixture/attempt_001/events.jsonl", b"synthetic log"),
                     response=self.raw("fixture/attempt_001/response.json", b"{}"))
        self.save(bundle)
        return bundle

    def test_c15_actual_files_and_independent_binding_never_formal(self):
        self.setup_ref()
        for kind in ("chat_native_web", "codex_cli", "manual"):
            with self.subTest(kind=kind):
                bundle = self.fixture(kind)
                pending = self.audit()
                self.assertEqual(pending["status"], "pending_independent_execution_binding")
                self.assertFalse(pending["formal_eligible"])
                report = self.audit(self.expected(bundle))
                self.assertEqual(report["status"], "records_hash_bound_pending_source_verification")
                self.assertTrue(report["checked_files"])
                self.assertFalse(report["formal_eligible"])

    def test_c15_tampered_record_and_result_rejected(self):
        self.setup_ref()
        bundle = self.fixture()
        expected = self.expected(bundle)
        self.raw("fixture/chat_record.txt", b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.audit(expected)
        bundle = self.fixture()
        expected = self.expected(bundle)
        bundle["failure_reasons"].append("changed result")
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "binding does not match"):
            self.audit(expected)

    def test_c15_missing_records_and_model_booleans(self):
        self.setup_ref()
        bundle = dict(result(), task_snapshot=self.ref)
        self.save(bundle)
        self.assertEqual(self.audit()["status"], "pending_missing_original_records")
        bundle["formal_eligible"] = True
        self.save(bundle)
        with self.assertRaises(ValidationError):
            self.audit()
        bundle = self.fixture()
        (self.work / "fixture/chat_record.txt").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or out-of-namespace"):
            self.audit()

    def test_c15_wrong_task_and_superseded_version(self):
        self.setup_ref()
        bundle = self.fixture()
        expected = self.expected(bundle)
        wrong = deepcopy(expected)
        wrong["task_snapshot"]["task_id"] = "other-task"
        with self.assertRaisesRegex(ValueError, "binding does not match"):
            self.audit(wrong)
        bundle["task_snapshot"]["research_id"] = "other_fixture"
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "selected task snapshot"):
            self.audit()
        self.fixture()
        task_packet.freeze_packet(self.make_packet(research_question="New question"),
                                  current_run_id="offline_fixture")
        with self.assertRaisesRegex(ValueError, "Superseded"):
            self.audit()

    def test_c15_paths_and_attempt_isolation(self):
        self.setup_ref()
        bundle = self.fixture("codex_cli")
        bundle["provenance"]["response"] = self.raw("fixture/attempt_002/response.json", b"{}")
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "different attempts"):
            self.audit()
        bundle = self.fixture()
        bundle["provenance"]["record_refs"][0]["path"] = "../outside.txt"
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.audit()
        bundle = self.fixture()
        outside = self.root / "outside.txt"
        outside.write_bytes(b"outside")
        link = self.work / "fixture/link.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink unavailable")
        bundle["provenance"]["record_refs"] = [{"path": "fixture/link.txt",
            "sha256": hashlib.sha256(b"outside").hexdigest()}]
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "out-of-namespace"):
            self.audit()

    def test_c15_failed_execution_and_wrong_hash_binding(self):
        self.setup_ref()
        bundle = self.fixture("codex_cli")
        bundle["provenance"]["exit_code"] = 1
        self.save(bundle)
        self.assertEqual(self.audit(self.expected(bundle))["status"], "execution_failed")
        expected = self.expected(bundle)
        expected["result_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "binding does not match"):
            self.audit(expected)


if __name__ == "__main__":
    unittest.main()
