import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import test_review_binding
from review_reject_plan import rejection_contract, plan_candidate_rejection, original_academic_route
import ai_paper5_strict as strict


class RejectRouteTests(unittest.TestCase):
    def test_actual_original_revision_limit(self):
        for history, expected in (([], "S03"), ([{"outcome":"value"}], "S03"),
            ([{"outcome":"value"},{"outcome":"concept"}], "eliminated")):
            self.assertEqual(original_academic_route(strict, {"history":history}, "value"), expected)

    def test_missing_data_and_technical_are_not_reject(self):
        state={"status":"preliminary_review","history":[]}
        ctx={"review_kind":"preliminary_academic","gate_ref":"00/v009 staged_topic.review:preliminary_review"}
        for x in ("missing_data","materials_pending","technical",None):
            with self.assertRaises(ValueError): rejection_contract(strict,state,ctx,x)

    def test_module_rejection_does_not_terminate_topic(self):
        state={"status":"frozen"}
        ctx={"review_kind":"empirical_matrix","gate_ref":"00/v009 resume_writing.resume"}
        self.assertIsNone(rejection_contract(strict,state,ctx,None)["possible_original_state"])
        with self.assertRaises(ValueError): rejection_contract(strict,state,ctx,"concept")


class RejectCandidateTests(unittest.TestCase):
    setUp=test_review_binding.ReviewBindingTest.setUp
    write=test_review_binding.ReviewBindingTest.write
    sync=test_review_binding.ReviewBindingTest.sync

    def test_candidate_reasons_persist_no_archive(self):
        self.context["gate_ref"]="00/v009 resume_writing.resume"
        self.snapshot["packet"]["input_files"][0]=self.write("context.json",self.context)
        self.report.update(decision="reject",reason="Synthetic academic defect",evidence_findings=[],issues=[
            {"issue_id":"I1","dimension_id":"D1","category":"academic_defect","blocking":True,
             "detail":"Synthetic problem","required_action":"Stop and reassess","evidence_ids":["M1"]}])
        self.sync()
        self.task_packet.heritage.state_of=Mock(return_value={"status":"frozen"})
        self.task_packet.heritage.read=strict.read
        import hashlib
        self.task_packet._digest=lambda v: hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
        self.task_packet._atomic_json=strict.write
        result=plan_candidate_rejection("report.json",current_run_id=self.run.name,
            expected_reference=self.reference,context_path="context.json")
        self.assertEqual(result["reason"],"Synthetic academic defect")
        self.assertFalse(result["terminate_run"])
        self.assertFalse(result["archive_authorized"])
        self.assertEqual(strict.read(self.run/result["candidate_path"])["blocking_issues"][0]["issue_id"],"I1")
        self.assertEqual(result,plan_candidate_rejection("report.json",current_run_id=self.run.name,
            expected_reference=self.reference,context_path="context.json"))


if __name__=="__main__": unittest.main()
