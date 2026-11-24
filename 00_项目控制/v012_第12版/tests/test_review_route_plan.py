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


if __name__ == "__main__":
    unittest.main()
