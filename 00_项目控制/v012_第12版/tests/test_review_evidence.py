import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_evidence import SCHEMA, audit_review_evidence


class ReviewEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.path = self.run / "receipt.json"
        self.path.write_text(json.dumps({"materials": [{"material_id": "M1", "text": "sample"},
                                                        {"material_id": "M2", "text": "counterexample"}]}), encoding="utf-8")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.context = {"review_kind": "empirical_matrix",
                        "input_materials": [{"artifact_id": "receipt", "path": "receipt.json", "sha256": self.sha}],
                        "review_dimensions": [{"dimension_id": "D1"}], "key_claims": [{"claim_id": "C1"}],
                        "evidence_scope": {"allowed_ids": ["M1", "M2"], "excluded_or_pending_ids": ["M3"]}}
        evidence = {"evidence_id": "M1", "artifact_id": "receipt", "path": "receipt.json", "sha256": self.sha,
                    "locator": {"kind": "json_pointer", "pointer": "/materials/0"}, "relation": "support",
                    "support_scope": "Only the stated sample"}
        self.report = {"schema_version": 4, "review_type": "academic_review", "prior_review": None, "reviewer": {"executor": "codex_cli", "reviewer_id": "fixture",
                       "model": "fixture-model", "invocation_id": "fixture-call"}, "execution_id": "fixture-attempt",
                       "task_snapshot": {"research_id": "r", "stage_id": "s", "task_id": "t",
                       "snapshot_sha256": "a"*64}, "review_kind": "empirical_matrix", "decision": "pass",
                       "reason": "Scoped assessment", "issues": [], "assessment_scope": "D1 only",
                       "evidence_findings": [{"dimension_id": "D1", "claim_id": "C1", "status": "limited",
                       "blocking": False, "reason": "limited support", "scope_limit": "sample only",
                       "evidence": [evidence], "counterexample_review": "No counterexample in this submitted record",
                       "unresolved_questions": []}]}

    def audit(self):
        return audit_review_evidence(self.run, self.context, self.report)

    def reject(self):
        with self.assertRaises((ValueError, ValidationError, OSError)):
            self.audit()

    def test_schema_valid_and_scoped_pass(self):
        Draft202012Validator.check_schema(json.loads(SCHEMA.read_text()))
        self.assertFalse(self.audit()["formal_eligible"])

    def test_real_counterexample_and_nonblocking_question(self):
        f = self.report["evidence_findings"][0]
        e = copy.deepcopy(f["evidence"][0])
        e.update(evidence_id="M2", relation="counterexample", locator={"kind": "json_pointer", "pointer": "/materials/1"})
        f["evidence"].append(e)
        f["unresolved_questions"] = [{"question": "Generalization?", "blocking": False, "reason": "Outside scope"}]
        self.audit()

    def test_pass_without_evidence(self):
        self.report["evidence_findings"] = []
        self.reject()

    def test_pass_with_blocking_question(self):
        self.report["evidence_findings"][0]["unresolved_questions"] = [{"question": "Missing evidence", "blocking": True, "reason": "Core"}]
        self.reject()

    def test_fabricated_or_pending_id(self):
        for eid in ("FAKE", "M3"):
            with self.subTest(eid=eid):
                self.report["evidence_findings"][0]["evidence"][0]["evidence_id"] = eid
                self.reject()

    def test_mismatched_locator(self):
        self.report["evidence_findings"][0]["evidence"][0]["locator"]["pointer"] = "/materials/1"
        self.reject()

    def test_missing_locator(self):
        self.report["evidence_findings"][0]["evidence"][0]["locator"]["pointer"] = "/materials/2"
        self.reject()

    def test_changed_bytes(self):
        self.path.write_text("{}")
        self.reject()

    def test_wrong_hash(self):
        self.report["evidence_findings"][0]["evidence"][0]["sha256"] = "b"*64
        self.reject()

    def test_missing_required_claim(self):
        self.context["key_claims"].append({"claim_id": "C2"})
        self.reject()

    def test_missing_required_dimension(self):
        self.context["review_dimensions"].append({"dimension_id": "D2"})
        self.reject()

    def test_missing_support(self):
        self.report["evidence_findings"][0]["evidence"][0]["relation"] = "context"
        self.reject()

    def test_missing_counterexample_review(self):
        del self.report["evidence_findings"][0]["counterexample_review"]
        self.reject()

    def test_need_evidence_with_real_gap(self):
        f = self.report["evidence_findings"][0]
        f.update(status="unresolved", blocking=True, evidence=[], unresolved_questions=[{"question": "Missing source?", "blocking": True, "reason": "Core"}])
        self.report.update(decision="need_evidence", issues=[{"issue_id": "I1", "dimension_id": "D1", "category": "evidence_gap", "blocking": True, "detail": "Missing source", "evidence_ids": ["M3"], "required_action": "Request evidence"}])
        self.audit()

    def test_unable_without_fabrication(self):
        self.report.update(decision="unable_to_review", evidence_findings=[], issues=[{"issue_id": "I1", "dimension_id": "D1", "category": "execution_blocker", "blocking": True, "detail": "No access", "evidence_ids": [], "required_action": "Stop"}])
        self.audit()

    def test_old_version_rejected(self):
        self.report["schema_version"] = 3
        self.reject()

    def test_line_locator_out_of_bounds(self):
        self.report["evidence_findings"][0]["evidence"][0]["locator"] = {"kind": "lines", "start": 1, "end": 2}
        self.reject()

    def test_wrong_artifact_path(self):
        self.report["evidence_findings"][0]["evidence"][0]["path"] = "../receipt.json"
        self.reject()

    def test_duplicate_findings(self):
        self.report["evidence_findings"].append(copy.deepcopy(self.report["evidence_findings"][0]))
        self.reject()


if __name__ == "__main__":
    unittest.main()
