import unittest
from unittest.mock import Mock
import test_review_binding
from review_evidence_return import plan_candidate_evidence, evidence_routes


class EvidenceReturnTests(unittest.TestCase):
    setUp=test_review_binding.ReviewBindingTest.setUp
    write=test_review_binding.ReviewBindingTest.write
    sync=test_review_binding.ReviewBindingTest.sync

    def prepare(self):
        ref=self.write("qualitative_framework/attempt_001/material_receipt.json",{"fixture":True})
        self.context.update(gate_ref="00/v009 resume_writing.resume")
        self.context["input_materials"].append({"artifact_id":"framework_receipt",**ref})
        self.snapshot["packet"]["input_files"].append(ref)
        self.snapshot["packet"]["input_files"][0]=self.write("context.json",self.context)
        finding=self.report["evidence_findings"][0]
        finding.update(status="unresolved",blocking=True,unresolved_questions=[{
            "question":"Synthetic missing event?", "blocking":True, "reason":"No independent supporting event"}])
        self.report.update(decision="need_evidence",issues=[{"issue_id":"I1","dimension_id":"D1",
            "category":"evidence_gap","blocking":True,"detail":"Missing event",
            "required_action":"Find independent supporting or counterexample event","evidence_ids":["M1"]}])
        self.sync()
        self.task_packet.heritage.state_of=Mock(return_value={"status":"frozen"})

    def plan(self,mapping):
        return plan_candidate_evidence("report.json",current_run_id=self.run.name,
            expected_reference=self.reference,context_path="context.json",gap_routes=mapping)

    def test_material_evidence_return_not_polish(self):
        self.prepare()
        result=self.plan({"I1":"event"})
        self.assertIn("repair_materials",result["evidence_tasks"][0]["route"]["original_entry"])
        self.assertFalse(result["execute_search"])
        self.assertFalse(result["writing_authorized"])
        self.assertFalse(result["text_polish_substitutes_evidence"])

    def test_no_polish_or_unavailable_route(self):
        self.prepare()
        for route in ("polish","literature","draft"):
            with self.assertRaises(ValueError): self.plan({"I1":route})

    def test_every_gap_requires_route(self):
        self.prepare()
        for m in ({},{"I1":"event","I2":"event"}):
            with self.assertRaises(ValueError): self.plan(m)

    def test_original_literature_phase_not_new_quota(self):
        for kind,expected in (("preliminary_academic","initial"),("final_research","supplemental")):
            routes=evidence_routes({"review_kind":kind,"input_materials":[]},{"status":"final_review" if kind=="final_research" else "preliminary_review"})
            self.assertEqual(routes["literature"]["required_original_phase"],expected)
            self.assertTrue(routes["literature"]["requires_original_phase_authorization"])


if __name__=="__main__": unittest.main()
