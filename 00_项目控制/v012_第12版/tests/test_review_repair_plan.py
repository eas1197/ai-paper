import unittest
from unittest.mock import Mock
import test_review_binding
from review_repair_plan import plan_candidate_revision


class RepairPlanTests(unittest.TestCase):
    setUp=test_review_binding.ReviewBindingTest.setUp
    write=test_review_binding.ReviewBindingTest.write
    sync=test_review_binding.ReviewBindingTest.sync

    def prepare(self):
        self.target="qualitative_framework/attempt_001/analysis_matrix.json"
        ref=self.write(self.target,{"fixture":True})
        self.context.update(gate_ref="00/v009 resume_writing.resume",input_binding={"selected_object":ref})
        self.context["input_materials"].append({"artifact_id":self.target,"role":"matrix",**ref})
        self.snapshot["packet"]["input_files"].append(ref)
        self.snapshot["packet"]["input_files"][0]=self.write("context.json",self.context)
        self.report.update(decision="revise",evidence_findings=[],issues=[{"issue_id":"I1","dimension_id":"D1",
            "category":"academic_defect","blocking":True,"detail":"Fixture argument too broad",
            "required_action":"Narrow conclusion","evidence_ids":["M1"]}])
        self.sync()
        self.task_packet.heritage.state_of=Mock(return_value={"status":"frozen"})

    def plan(self, mapping):
        return plan_candidate_revision("report.json",current_run_id=self.run.name,
            expected_reference=self.reference,context_path="context.json",target_map=mapping)

    def test_bound_revision_target_and_downstream(self):
        self.prepare()
        before=(self.run/self.target).read_bytes()
        result=self.plan({"I1":[self.target]})
        self.assertEqual(result["repair_tasks"][0]["problem"],"Fixture argument too broad")
        self.assertEqual(result["repair_tasks"][0]["targets"][0]["path"],self.target)
        self.assertIn("autonomous_writing",[x["artifact"] for x in result["affected_downstream"]])
        self.assertFalse(result["execute_revision"])
        self.assertFalse(result["advance_gate"])
        self.assertEqual(before,(self.run/self.target).read_bytes())

    def test_raw_receipt_not_editable(self):
        self.prepare()
        with self.assertRaises(ValueError): self.plan({"I1":["receipt.json"]})

    def test_missing_or_extra_issue_rejected(self):
        self.prepare()
        for mapping in ({},{"I1":[self.target],"I2":[self.target]}):
            with self.assertRaises(ValueError): self.plan(mapping)

    def test_duplicate_or_unfrozen_target_rejected(self):
        self.prepare()
        for paths in ([self.target,self.target],["other.json"]):
            with self.assertRaises(ValueError): self.plan({"I1":paths})

    def test_pass_is_not_revision(self):
        self.prepare()
        self.report.update(decision="pass",issues=[])
        # Rejected either by candidate schema or decision routing; never produce repair.
        self.sync()
        with self.assertRaises(Exception): self.plan({"I1":[self.target]})


if __name__=="__main__": unittest.main()
