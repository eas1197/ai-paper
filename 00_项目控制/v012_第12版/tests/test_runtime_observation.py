import contextlib
import io
import json
import unittest
from unittest.mock import patch
import ai_paper5_strict as strict
import subprocess
from jsonschema import ValidationError
from run_observation import (STATES, observation, attempt_observation, command_observation,
    classify_failure, OriginalBudgetExhausted)


class RuntimeObservationTest(unittest.TestCase):
    def test_all_nine_statuses_never_grant_academic_approval(self):
        self.assertEqual(len(STATES),9)
        for status in STATES:
            value=observation(status,original_stage="fixture")
            self.assertEqual(value["runtime_status"],status)
            self.assertFalse(value["academic_approval_granted"])
            self.assertFalse(value["formal_eligible"])
        with self.assertRaises(ValueError): observation("pass")

    def test_attempt_only_uses_native_ledger(self):
        for record,expected in ((None,"queued"),({"status":"started"},"running"),
            ({"status":"completed"},"completed"),({"status":"technical_block"},"failed"),
            ({"status":"unknown"},"blocked")):
            self.assertEqual(attempt_observation(record)["runtime_status"],expected)

    def test_waits_and_unknown_are_not_completion(self):
        cases=(("chat-task",{},"waiting_for_chat"),("codex-task",{},"waiting_for_codex"),
            ("review-task",{},"waiting_for_review"),("status",{"status":"awaiting_original_quantitative_inputs"},"waiting_for_user"),
            ("advance",{"action":"await_independent_review","status":"blocked_by_original_v3_gate"},"waiting_for_review"),
            ("unknown",{"decision":"pass"},"blocked"),
            ("autopilot",{"result":{"status":"blocked_by_original_v3_gate"},"v3_stage":"preliminary_review"},"blocked"))
        for command,result,expected in cases:
            self.assertEqual(command_observation(command,result)["runtime_status"],expected)

    def test_i12_eight_failure_categories_are_distinct(self):
        cases = [
            (classify_failure(ConnectionError("network connection reset")), "network_failure"),
            (classify_failure(RuntimeError("Codex CLI not found")), "executor_unavailable"),
            (classify_failure(subprocess.TimeoutExpired("codex", 30)), "model_timeout"),
            (classify_failure(ValidationError("schema validation failed")), "schema_error"),
            (classify_failure(FileNotFoundError("missing source")), "evidence_missing"),
            (command_observation("advance", {"stage":"academic_stop"})["outcome_kind"], "academic_failure"),
            (classify_failure(OriginalBudgetExhausted("original budget exhausted")), "budget_exhausted"),
            (command_observation("advance", {"status":"cancelled_by_user"})["outcome_kind"], "user_cancelled"),
        ]
        self.assertEqual([value for value, _ in cases], [expected for _, expected in cases])
        self.assertEqual(len({value for value, _ in cases}), 8)
        self.assertEqual(classify_failure(RuntimeError("external allowance exhausted")), "technical_failure")

    def test_i12_structured_failure_kind_survives_command_observation(self):
        for kind in ("network_failure","executor_unavailable","model_timeout","schema_error","evidence_missing"):
            result = command_observation("autopilot", {"status":"execution_failed","failure_kind":kind})
            self.assertEqual(result["outcome_kind"], kind)
            self.assertEqual(result["runtime_status"], "blocked" if kind=="evidence_missing" else "failed")
            self.assertFalse(result["academic_approval_granted"])

    def test_cli_exit_zero_can_be_waiting(self):
        result={"action":"await_independent_review","status":"blocked_by_original_v3_gate"}
        output=io.StringIO()
        with patch.object(strict,"status",return_value=result),contextlib.redirect_stdout(output):
            self.assertEqual(strict.main(["advance","--run-id","fixture"]),0)
        body=json.loads(output.getvalue())
        self.assertEqual(body["runtime"]["runtime_status"],"waiting_for_review")
        self.assertFalse(body["runtime"]["academic_approval_granted"])


if __name__=="__main__": unittest.main()
