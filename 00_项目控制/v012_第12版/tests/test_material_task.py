"""F06 candidate generation; real C04, original verification mocked at boundary."""
import unittest
import test_frozen_route as fixture
from unittest.mock import patch
import ai_paper5_strict as strict
import task_packet as c
from material_task import prepare_material_task

class MaterialTaskTest(unittest.TestCase):
    setUp=fixture.FrozenRouteTest.setUp
    freeze=fixture.FrozenRouteTest.freeze

    def prepare_fixture(self,scope):
        self.freeze("online_qualitative")
        state=strict.state_of(self.run_id)
        final=state["history"][-1]
        final["material_scope"]=scope
        final["method_assessment"]["paths"]["online_qualitative"]["search_attempt"]="attempt_001"
        strict.write(self.work/"staged_topic.json",state)
        folder=self.work/"qualitative/attempt_001"
        for name,value in (("conversion.json",{"new_question":"Synthetic question"}),("material_receipt.json",{}),
                ("response.json",{}),("events.jsonl",{})):
            strict.write(folder/name,value)
        # Isolate the original verifier boundary, tested in E14/F05. No model call.
        with patch.object(strict,"frozen_route",return_value={"method":"online_qualitative"}), \
             patch.object(strict,"original_call",return_value='{"type":"object"}'):
            return prepare_material_task(self.run_id)

    def test_scope_candidate_frozen_no_search(self):
        scope={"target_objects":["fixture"],"events":["fixture"],"time_range":"fixture",
            "material_types":["fixture"],"exclusions":["fixture"]}
        result=self.prepare_fixture(scope)
        self.assertEqual(result["scope"],scope)
        self.assertEqual(result["unresolved_scope"],[])
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(result["task_packet"]["quantity_budget"],{})
        c.verify_snapshot(result["task_snapshot"],current_run_id=self.run_id)

    def test_missing_scope_stays_waiting(self):
        result=self.prepare_fixture({})
        self.assertEqual(len(result["unresolved_scope"]),5)
        self.assertEqual(result["status"],"waiting_for_user")
        self.assertFalse(result["dispatch_authorized"])

    def test_not_frozen_rejected(self):
        with self.assertRaisesRegex(ValueError,"must be frozen"):
            prepare_material_task(self.run_id)
