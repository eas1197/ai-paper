"""Offline review-class and revision lineage tests; no independent session is simulated as real."""
import copy
import unittest
import test_review_binding


class ReviewTypeTest(unittest.TestCase):
    setUp = test_review_binding.ReviewBindingTest.setUp
    write = test_review_binding.ReviewBindingTest.write
    sync = test_review_binding.ReviewBindingTest.sync
    audit = test_review_binding.ReviewBindingTest.audit
    reject = test_review_binding.ReviewBindingTest.reject

    def freeze_context(self):
        self.snapshot["packet"]["input_files"][0] = self.write("context.json", self.context)
        self.sync()

    def make_revision(self):
        prior = copy.deepcopy(self.report)
        prior["schema_version"] = 3
        prior.pop("review_type")
        prior.pop("prior_review")
        prior["task_snapshot"]["snapshot_sha256"] = "b"*64
        prior["execution_id"] = "prior-attempt"
        prior["decision"] = "revise"
        prior["issues"] = [{"issue_id": "I1", "dimension_id": "D1", "category": "academic_defect",
                           "blocking": True, "detail": "Scope too broad", "evidence_ids": ["M1"],
                           "required_action": "Narrow claim"}]
        old = self.write("old_receipt.json", {"materials": [{"material_id": "M1", "text": "Old"}]})
        current = {k: self.context["input_materials"][0][k] for k in ("path", "sha256")}
        prior_ref = self.write("prior.json", prior)
        self.revision = {"prior_report": prior_ref, "issues": [{"issue_id": "I1", "response": "Narrowed scope"}],
                         "changes": [{"before": old, "after": current}]}
        revision_ref = self.write("revision.json", self.revision)
        self.snapshot["packet"]["input_files"].extend([old, prior_ref, revision_ref])
        lineage = {"report": prior_ref, "revision": revision_ref}
        self.context.update(review_type="independent_re_review", prior_review=lineage)
        self.report.update(review_type="independent_re_review", prior_review=copy.deepcopy(lineage))
        self.freeze_context()

    def update_revision(self):
        ref = self.write("revision.json", self.revision)
        self.snapshot["packet"]["input_files"][-1] = ref
        self.report["prior_review"]["revision"] = ref
        self.context["prior_review"]["revision"] = ref
        self.freeze_context()

    def test_academic_candidate_only(self):
        result = self.audit()
        self.assertEqual(result["review_type_binding"]["review_type"], "academic_review")
        self.assertFalse(result["independent_review_verified"])

    def test_technical_and_format_cannot_submit_review(self):
        for kind in ("technical_verification", "format_check"):
            with self.subTest(kind=kind):
                self.report["review_type"] = kind
                self.context["review_type"] = kind
                self.freeze_context()
                self.reject()

    def test_frozen_type_mismatch(self):
        self.make_revision()
        self.report.update(review_type="academic_review", prior_review=None)
        self.sync()
        self.reject()

    def test_independent_rereview_candidate_with_lineage(self):
        self.make_revision()
        result = self.audit()
        self.assertEqual(result["review_type_binding"]["addressed_issue_ids"], ["I1"])
        self.assertFalse(result["formal_eligible"])
        self.assertFalse(result["independent_review_verified"])

    def test_rereview_requires_prior(self):
        self.report["review_type"] = "independent_re_review"
        self.sync()
        self.reject()

    def test_prior_report_changed(self):
        self.make_revision()
        self.write("prior.json", {"changed": True})
        self.reject()

    def test_revision_record_changed(self):
        self.make_revision()
        self.write("revision.json", {"changed": True})
        self.reject()

    def test_revision_must_address_issues(self):
        self.make_revision()
        self.revision["issues"] = []
        self.update_revision()
        self.reject()

    def test_no_unchanged_revision(self):
        self.make_revision()
        self.revision["changes"][0]["before"] = self.revision["changes"][0]["after"]
        self.update_revision()
        self.reject()

    def test_new_snapshot_required(self):
        self.make_revision()
        self.reference["snapshot_sha256"] = "b"*64
        self.sync()
        self.reject()

    def test_no_reused_execution(self):
        self.make_revision()
        self.report["execution_id"] = "prior-attempt"
        self.receipt["execution_id"] = "prior-attempt"
        self.sync()
        self.reject()


if __name__ == "__main__":
    unittest.main()
