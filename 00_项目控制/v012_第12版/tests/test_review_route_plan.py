"""D23 candidate-routing tests; original positive transitions are tested by v009."""
import copy
import types
import unittest
from unittest.mock import Mock
import test_review_binding
from review_route_plan import pass_contract, plan_candidate_pass


class PassRouteTests(unittest.TestCase):
    def test_original_initial_and_final_routes(self):
        for stage,kind,phase,targets in (
            ("preliminary_review","preliminary_academic",None,["design_review","supplemental"]),
            ("design_review","research_design",None,["supplemental"]),
            ("final_review","final_research",None,["s08_ready"]),
            ("materials_pending","final_research","final",["s08_ready"]),
            ("S03","preliminary_academic","initial",["design_review","supplemental"]),
        ):
            with self.subTest(stage=stage):
                route=pass_contract({"status":stage,"review_phase":phase},
                    {"review_kind":kind,"gate_ref":"00/v009 staged_topic.review:"+stage})
                self.assertEqual(route["possible_original_states"],targets)
                self.assertTrue(route["native_report_required"])

    def test_wrong_state_and_gate_rejected(self):
        for state,ctx in (
            ({"status":"frozen"},{"review_kind":"final_research","gate_ref":"00/v009 staged_topic.review:frozen"}),
            ({"status":"final_review"},{"review_kind":"preliminary_academic","gate_ref":"00/v009 staged_topic.review:final_review"}),
            ({"status":"design_review"},{"review_kind":"research_design","gate_ref":"fake"}),
            ({"status":"frozen"},{"review_kind":"event_fact","gate_ref":"fake"}),
        ):
            with self.subTest(ctx=ctx), self.assertRaises(ValueError): pass_contract(state,ctx)

    def test_module_routes_do_not_mutate_topic(self):
        for stage,kind,gate in (
            ("design_review","qualitative_design","06/v005 qual_materials.record_review"),
            ("frozen","empirical_matrix","00/v009 resume_writing.resume"),
            ("frozen","writing_plan","00/v009 resume_writing.resume + V15"),
            ("frozen","qualitative_g7","V16 writing_review_request"),
        ):
            with self.subTest(kind=kind):
                route=pass_contract({"status":stage},{"review_kind":kind,"gate_ref":gate})
                self.assertEqual(route["possible_original_states"],[])
                if kind=="qualitative_g7": self.assertIsNone(route["native_handler"])


class CandidatePassTests(unittest.TestCase):
    setUp=test_review_binding.ReviewBindingTest.setUp
    write=test_review_binding.ReviewBindingTest.write
    sync=test_review_binding.ReviewBindingTest.sync

    def test_candidate_pass_never_authorizes(self):
        self.context["gate_ref"]="00/v009 resume_writing.resume"
        self.snapshot["packet"]["input_files"][0]=self.write("context.json",self.context)
        self.task_packet.heritage.state_of=Mock(return_value={"status":"frozen"})
        result=plan_candidate_pass("report.json",current_run_id=self.run.name,expected_reference=self.reference,context_path="context.json")
        self.assertEqual(result["status"],"awaiting_independent_authorization")
        self.assertFalse(result["advance_gate"])
        self.assertFalse(result["formal_eligible"])
        self.assertFalse(result["independent_review_verified"])
        self.assertIn("material_adequacy",result["route"]["native_handler"])

    def test_candidate_cannot_use_stale_context(self):
        self.context["gate_ref"]="fake"
        self.write("context.json",self.context)
        with self.assertRaisesRegex(ValueError,"bytes changed"):
            plan_candidate_pass("report.json",current_run_id=self.run.name,expected_reference=self.reference,context_path="context.json")


class QualitativeG7IntakeTests(unittest.TestCase):
    setUp = test_review_binding.ReviewBindingTest.setUp
    write = test_review_binding.ReviewBindingTest.write
    sync = test_review_binding.ReviewBindingTest.sync

    def prepare(self):
        self.context.update(review_kind="qualitative_g7", gate_ref="V16 writing_review_request")
        self.report["review_kind"] = "qualitative_g7"
        self.snapshot["packet"]["input_files"][0] = self.write("context.json", self.context)
        self.sync()
        self.task_packet.heritage.state_of = Mock(return_value={"status": "frozen"})

    def plan(self, **kwargs):
        from review_route_plan import plan_qualitative_g7_decision
        return plan_qualitative_g7_decision("report.json", current_run_id=self.run.name,
            expected_reference=self.reference, context_path="context.json", **kwargs)

    def test_g24_pass_candidate_cannot_authorize_formal_g7(self):
        self.prepare()
        result = self.plan()
        self.assertEqual(result["next_action"], "await_independent_authorization")
        self.assertIsNone(result["route"]["native_handler"])
        self.assertEqual(result["status"], "blocked_by_independent_authorization")
        for key in ("formal_pass", "formal_eligible", "independent_review_verified", "advance_gate",
                    "execute_revision", "execute_search", "search_authorized", "terminate_run", "automatic_retry"):
            self.assertFalse(result[key])

    def test_g24_revise_reuses_bound_repair_targets(self):
        self.prepare()
        manuscript = self.write("writer4/draft.md", {"fixture": "draft"})
        ledger = self.write("writer4/claims.json", {"fixture": "ledger"})
        request = self.write("writer4/writing_review_request.json",
            {"manuscript_sha256": manuscript["sha256"], "claim_ledger_sha256": ledger["sha256"]})
        self.context["input_binding"] = {"selected_object": request}
        for ref in (manuscript, ledger, request):
            self.context["input_materials"].append({"artifact_id": ref["path"], "role": "fixture", **ref})
            self.snapshot["packet"]["input_files"].append(ref)
        self.snapshot["packet"]["input_files"][0] = self.write("context.json", self.context)
        self.report.update(decision="revise", evidence_findings=[], issues=[{"issue_id": "I1",
            "dimension_id": "D1", "category": "academic_defect", "blocking": True, "detail": "Too broad",
            "required_action": "Narrow", "evidence_ids": ["M1"]}])
        self.sync()
        result = self.plan(target_map={"I1": [manuscript["path"], ledger["path"]]})
        self.assertEqual(result["next_action"], "candidate_revision")
        self.assertEqual(result["candidate"]["repair_tasks"][0]["targets"][0]["sha256"], manuscript["sha256"])
        self.assertFalse(result["execute_revision"])
        self.assertFalse(result["formal_pass"])
        with self.assertRaises(ValueError):
            self.plan(target_map={"I1": ["receipt.json"]})

    def test_g24_unable_stays_waiting(self):
        self.prepare()
        self.report.update(decision="unable_to_review", reviewer=None, execution_id=None, evidence_findings=[],
            issues=[{"issue_id": "I1", "dimension_id": "D1", "category": "execution_blocker", "blocking": True,
                     "detail": "No session", "required_action": "Stop", "evidence_ids": []}])
        self.sync()
        result = self.plan()
        self.assertEqual(result["next_action"], "await_independent_review")
        self.assertFalse(result["advance_gate"])
        self.assertFalse(result["automatic_retry"])

    def test_g24_no_wrong_gate_stale_snapshot_or_receiver_override(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.plan(target_map={"I1": ["receipt.json"]})
        self.task_packet.heritage.state_of.return_value = {"status": "design_review"}
        with self.assertRaises(ValueError):
            self.plan()
        self.task_packet.heritage.state_of.return_value = {"status": "frozen"}
        self.context["gate_ref"] = "00/v009 resume_writing.resume"
        self.snapshot["packet"]["input_files"][0] = self.write("context.json", self.context)
        with self.assertRaises(ValueError):
            self.plan()
        self.task_packet.verify_snapshot.side_effect = ValueError("Superseded snapshot")
        with self.assertRaisesRegex(ValueError, "Superseded"):
            self.plan()


if __name__ == "__main__":
    unittest.main()
