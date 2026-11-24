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

    def test_g22_five_g7_issue_types_produce_bound_revision_tasks(self):
        from review_repair_plan import G7_REPAIR_GUIDANCE
        manuscript = "writer4/draft.md"
        claims = "writer4/claims.json"
        request = "writer4/writing_review_request.json"
        draft_ref = self.write(manuscript, {"fixture": "draft"})
        claims_ref = self.write(claims, {"fixture": "claims"})
        req_ref = self.write(request, {"manuscript_sha256": draft_ref["sha256"],
                                       "claim_ledger_sha256": claims_ref["sha256"]})
        self.context.update(review_kind="qualitative_g7", gate_ref="V16 writing_review_request",
                            input_binding={"selected_object": req_ref},
                            review_dimensions=[{"dimension_id": key} for key in G7_REPAIR_GUIDANCE])
        for item in (draft_ref, claims_ref, req_ref):
            self.context["input_materials"].append({"artifact_id": item["path"], "role": "fixture", **item})
            self.snapshot["packet"]["input_files"].append(item)
        self.snapshot["packet"]["input_files"][0] = self.write("context.json", self.context)
        issues = [{"issue_id": "I"+str(i), "dimension_id": key, "category": "academic_defect",
                   "blocking": True, "detail": "Fixture defect "+key,
                   "required_action": "Revise stated defect", "evidence_ids": ["M1"]}
                  for i, key in enumerate(G7_REPAIR_GUIDANCE)]
        self.report.update(review_kind="qualitative_g7", decision="revise", evidence_findings=[], issues=issues)
        self.sync()
        self.task_packet.heritage.state_of=Mock(return_value={"status":"frozen"})
        result=self.plan({issue["issue_id"]:[manuscript,claims] for issue in issues})
        self.assertEqual(len(result["repair_tasks"]),5)
        for task in result["repair_tasks"]:
            self.assertEqual(task["revision_guidance"],G7_REPAIR_GUIDANCE[task["dimension_id"]])
            self.assertTrue(task["resubmit_required"])
            self.assertTrue(task["independent_re_review_required"])
            self.assertEqual([item["sha256"] for item in task["targets"]],
                             [draft_ref["sha256"],claims_ref["sha256"]])
        self.assertFalse(result["execute_revision"])
        self.assertFalse(result["advance_gate"])
        self.assertFalse(result["formal_eligible"])
        with self.assertRaises(ValueError):
            self.plan({issue["issue_id"]:["receipt.json"] for issue in issues})

    def test_pass_is_not_revision(self):
        self.prepare()
        self.report.update(decision="pass",issues=[])
        # Rejected either by candidate schema or decision routing; never produce repair.
        self.sync()
        with self.assertRaises(Exception): self.plan({"I1":[self.target]})


if __name__=="__main__": unittest.main()
