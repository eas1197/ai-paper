"""E21 tests: distinct observation outcomes, not academic decisions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from run_observation import command_observation,attempt_observation

class StopOutcomesTest(unittest.TestCase):
    def test_five_distinct_outcomes(self):
        cases=[
            ({"stage":"eliminated"},"academic_failure"),
            ({"status":"execution_failed"},"technical_failure"),
            ({"status":"blocked_by_original_v3_gate","action":"await_independent_review",
              "wait":{"reason_code":"invalid_or_incomplete_records"}},"evidence_missing"),
            ({"stage":"literature_budget_exhausted","status":"waiting_for_user"},"budget_exhausted"),
            ({"status":"cancelled_by_user","stage":"initial"},"user_cancelled"),
        ]
        for value,expected in cases:
            with self.subTest(expected=expected):
                result=command_observation("advance",value)
                self.assertEqual(result["outcome_kind"],expected)
                self.assertFalse(result["academic_approval_granted"])
                self.assertFalse(result["formal_eligible"])
    def test_wait_is_not_review_failure(self):
        result=command_observation("advance",{"action":"await_independent_review","wait":{"reason_code":"missing_independent_records"}})
        self.assertEqual(result["runtime_status"],"waiting_for_review")
        self.assertIsNone(result["outcome_kind"])
    def test_native_failure_is_technical(self):
        self.assertEqual(attempt_observation({"status":"failed"})["outcome_kind"],"technical_failure")
