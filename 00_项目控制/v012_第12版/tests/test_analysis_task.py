"""F12 original candidate schemas and current receipt binding (synthetic only)."""
import unittest
import json
from unittest.mock import patch
import test_frozen_route as fixture
import ai_paper5_strict as strict
import task_packet as c
from analysis_task import prepare_analysis_task

class AnalysisTaskTest(unittest.TestCase):
    setUp=fixture.FrozenRouteTest.setUp
    freeze=fixture.FrozenRouteTest.freeze
    def fixture_inputs(self):
        self.freeze("online_qualitative")
        state=strict.state_of(self.run_id)
        state["history"][-1]["method_assessment"]["paths"]["online_qualitative"]["search_attempt"]="attempt_001"
        strict.write(self.work/"staged_topic.json",state)
        conversion={"new_question":state["question"],"core_question":"Fixture core"}
        framework={"core_question":"Fixture core","dimensions":[{"id":"D1"}]}
        for area in ("qualitative","qualitative_framework"):
            folder=self.work/area/"attempt_001"
            strict.write(folder/"conversion.json",conversion)
            strict.write(folder/"events.jsonl",{"fixture":True})
            strict.write(folder/"response.json",{"fixture":True})
            receipt={"run_id":self.run_id,"status":"pending_independent_review","conversion_sha256":c._digest(conversion),
                "events_sha256":strict.sha(folder/"events.jsonl"),"response_sha256":strict.sha(folder/"response.json"),
                "tool_events":1,"materials":[{"material_id":"M1"}]}
            if area=="qualitative_framework":
                strict.write(folder/"framework.json",framework)
                receipt.update(phase="framework_collection",framework_sha256=c._digest(framework))
            strict.write(folder/"material_receipt.json",receipt)
    def prepare(self,kind):
        spec=[["core_question","core_concept"],["id","name"],["conclusion","boundary","unresolved","alternatives"],["support","counterexample","competing","context"]]
        with patch.object(strict,"frozen_route",return_value={"method":"online_qualitative"}),patch.object(strict,"original_call",return_value=json.dumps(spec)),patch("analysis_task._original_binding",return_value={"fixture":True}):
            return prepare_analysis_task(self.run_id,kind)
    def test_framework_and_matrix_candidates_freeze_inputs(self):
        self.fixture_inputs()
        for kind in ("framework","matrix"):
            result=self.prepare(kind)
            self.assertFalse(result["dispatch_authorized"])
            packet=c.verify_snapshot(result["task_snapshot"],current_run_id=self.run_id)["packet"]
            self.assertEqual(packet["quantity_budget"],{})
            self.assertEqual(packet["output_schema"]["schema"]["type"],"object" if kind=="framework" else "array")
            if kind=="matrix":
                self.assertEqual(packet["output_schema"]["schema"]["items"]["properties"]["dimension_id"]["enum"],["D1"])
    def test_changed_original_receipt_rejected(self):
        self.fixture_inputs()
        strict.write(self.work/"qualitative_framework/attempt_001/response.json",{"changed":True})
        with self.assertRaisesRegex(ValueError,"receipt or original bytes differ"):
            self.prepare("matrix")
