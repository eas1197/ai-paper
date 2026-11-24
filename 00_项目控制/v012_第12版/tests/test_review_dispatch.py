"""E12: real D21/C04/D18 offline scheduling; synthetic pre-gate inputs only."""
import unittest
from unittest.mock import Mock, patch
import ai_paper5_strict as strict
import autopilot_v3
from test_review_task_integration import OriginalReviewTaskIntegration


class ReviewDispatchTest(unittest.TestCase):
    setUp=OriginalReviewTaskIntegration.setUp
    set_stage=OriginalReviewTaskIntegration.set_stage

    def test_all_three_gates_prepare_and_wait_without_model(self):
        for phase,kind in (("preliminary_review","preliminary_academic"),("design_review","research_design"),
                           ("final_review","final_research")):
            with self.subTest(phase=phase):
                self.set_stage(phase)
                before=(self.work/"staged_topic.json").read_bytes()
                engine=Mock()
                result=autopilot_v3.step(self.run_id,executor=engine)
                self.assertEqual(result["status"],"blocked_by_original_v3_gate")
                self.assertEqual(result["wait"]["status"],"unable_to_review")
                self.assertFalse(result["advance_gate"])
                self.assertFalse(result["automatic_retry"])
                self.assertEqual(strict.read(self.work/result["candidate"]["context_path"])["review_kind"],kind)
                self.assertEqual(result,autopilot_v3.step(self.run_id,executor=engine))
                self.assertEqual(result,strict.status(self.run_id,progress=True))
                self.assertEqual(before,(self.work/"staged_topic.json").read_bytes())
                engine.call.assert_not_called()

    def test_native_search_transition_schedules_review_without_another_search(self):
        transition={"action":"original_native_literature_search","after":"preliminary_review"}
        wait={"status":"blocked_by_original_v3_gate","advance_gate":False}
        with patch.object(strict,"state_of",return_value={"status":"initial"}),patch.object(strict,"status",side_effect=[transition,wait]) as call:
            result=autopilot_v3.step(self.run_id,executor=Mock())
        self.assertEqual(result["original_transition"],transition)
        self.assertFalse(result["advance_gate"])
        self.assertEqual(call.call_count,2)

    def test_missing_original_review_inputs_stop(self):
        self.set_stage("preliminary_review")
        (self.work/"initial/literature_matrix.json").unlink()
        engine=Mock()
        with self.assertRaises(ValueError):
            autopilot_v3.step(self.run_id,executor=engine)
        engine.call.assert_not_called()


if __name__=="__main__": unittest.main()
