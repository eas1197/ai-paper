"""Offline contract fixtures; C04 is separately responsible for real snapshot validity."""
import copy
import hashlib
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import test_review_evidence
from review_binding import audit_review_binding
from jsonschema import ValidationError


class ReviewBindingTest(unittest.TestCase):
    def setUp(self):
        fixture = test_review_evidence.ReviewEvidenceTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.run, self.context, self.report = fixture.run, fixture.context, fixture.report
        self.reference = self.report["task_snapshot"]
        self.reference["research_id"] = self.run.name
        self.context["research_question"] = "Fixture question"
        context_ref = self.write("context.json", self.context)
        self.snapshot = {"packet": {"research_question": "Fixture question",
                                    "input_files": [context_ref, {"path": "receipt.json", "sha256": fixture.sha}]}}
        self.task_packet = types.ModuleType("task_packet")
        self.task_packet.heritage = types.SimpleNamespace(RUNS=self.run.parent)
        self.task_packet.verify_snapshot = Mock(return_value=self.snapshot)
        patcher = patch.dict(sys.modules, {"task_packet": self.task_packet})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.receipt = {"schema_version": 1, "execution_id": self.report["execution_id"],
                        "task_snapshot": self.reference, "reviewer": copy.deepcopy(self.report["reviewer"]),
                        "report": self.write("report.json", self.report), "status": "completed",
                        "records": [{"role": "events", **self.write("attempt/events.jsonl", {"fixture": True})},
                                    {"role": "response", **self.write("attempt/response.json", {"fixture": True})}]}
        self.receipt_ref = self.write("execution.json", self.receipt)

    def write(self, rel, value):
        path = self.run / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, ensure_ascii=False).encode()
        path.write_bytes(raw)
        return {"path": rel, "sha256": hashlib.sha256(raw).hexdigest()}

    def sync(self):
        self.receipt["report"] = self.write("report.json", self.report)
        self.receipt_ref = self.write("execution.json", self.receipt)

    def audit(self, **changes):
        args = {"current_run_id": self.run.name, "expected_reference": self.reference,
                "context_path": "context.json", "expected_execution_ref": self.receipt_ref}
        args.update(changes)
        return audit_review_binding("report.json", **args)

    def reject(self, **changes):
        with self.assertRaises((ValueError, ValidationError, OSError)):
            self.audit(**changes)

    def test_bound_not_independent(self):
        result = self.audit()
        self.assertEqual(result["status"], "review_records_hash_bound_pending_independence")
        self.assertFalse(result["independent_review_verified"])
        self.assertFalse(result["formal_eligible"])
        self.task_packet.verify_snapshot.assert_called_once_with(self.reference, current_run_id=self.run.name)

    def test_cross_identity(self):
        for key in ("research_id", "stage_id", "task_id", "snapshot_sha256"):
            with self.subTest(key=key):
                self.report["task_snapshot"] = dict(self.reference, **{key: "b"*64})
                self.sync()
                self.reject()

    def test_stale_snapshot_rejection_propagates(self):
        self.task_packet.verify_snapshot.side_effect = ValueError("Superseded task snapshot")
        with self.assertRaisesRegex(ValueError, "Superseded"):
            self.audit()

    def test_unfrozen_context(self):
        self.reject(context_path="other.json")

    def test_unfrozen_artifact(self):
        self.snapshot["packet"]["input_files"].pop()
        self.reject()

    def test_context_changed(self):
        self.context["research_question"] = "Changed"
        self.write("context.json", self.context)
        self.reject()

    def test_reviewer_mismatch(self):
        self.report["reviewer"]["invocation_id"] = "other"
        self.sync()
        self.reject()

    def test_execution_id_mismatch(self):
        self.report["execution_id"] = "other"
        self.sync()
        self.reject()

    def test_report_tampering(self):
        self.report["reason"] = "Changed"
        self.write("report.json", self.report)
        self.reject()

    def test_receipt_tampering(self):
        self.receipt["execution_id"] = "other"
        self.write("execution.json", self.receipt)
        self.reject()

    def test_original_record_tampering(self):
        self.write("attempt/events.jsonl", {"changed": True})
        self.reject()

    def test_missing_independent_record(self):
        self.reject(expected_execution_ref=None)

    def test_missing_original_record(self):
        self.receipt["records"].pop()
        self.sync()
        self.reject()

    def test_cross_attempt(self):
        self.receipt["records"][1] = {"role": "response", **self.write("another/response.json", {"fixture": True})}
        self.sync()
        self.reject()

    def test_failed_execution_no_pass(self):
        self.receipt["status"] = "failed"
        self.sync()
        self.reject()

    def test_unable_without_identity_or_record(self):
        self.report.update(decision="unable_to_review", reviewer=None, execution_id=None, evidence_findings=[],
                           issues=[{"issue_id": "I1", "dimension_id": "D1", "category": "execution_blocker",
                                    "blocking": True, "detail": "No session", "evidence_ids": [], "required_action": "Stop"}])
        self.write("report.json", self.report)
        result = self.audit(expected_execution_ref=None)
        self.assertEqual(result["status"], "pending_missing_execution_binding")
        self.assertFalse(result["formal_eligible"])

    def test_no_identity_for_pass(self):
        self.report.update(reviewer=None, execution_id=None)
        self.sync()
        self.reject()

    def test_record_reuse_rejected(self):
        self.receipt["records"][1] = {**self.receipt["records"][0], "role": "response"}
        self.sync()
        self.reject()


if __name__ == "__main__":
    unittest.main()
