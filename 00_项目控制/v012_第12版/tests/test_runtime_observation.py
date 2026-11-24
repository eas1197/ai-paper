import contextlib
import io
import json
import unittest
from unittest.mock import patch
import ai_paper5_strict as strict
import subprocess
from jsonschema import ValidationError
from run_observation import (STATES, observation, attempt_observation, command_observation,
    classify_failure, OriginalBudgetExhausted, recovery_policy, retry_decision)


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

    def test_i13_every_failure_has_explicit_nonautomatic_recovery_policy(self):
        expected = {
            "network_failure":"retryable", "model_timeout":"retryable",
            "executor_unavailable":"manual", "schema_error":"manual",
            "evidence_missing":"manual", "review_failure":"manual",
            "technical_failure":"manual", "academic_failure":"terminate",
            "research_failure":"terminate", "budget_exhausted":"terminate",
            "user_cancelled":"terminate",
        }
        for outcome, disposition in expected.items():
            with self.subTest(outcome=outcome):
                policy = recovery_policy(outcome)
                self.assertEqual(policy["disposition"], disposition)
                self.assertFalse(policy["automatic_retry"])
                self.assertFalse(policy["formal_eligible"])
                self.assertTrue(policy["next_action"])

    def test_i13_retry_requires_remaining_original_budget_new_attempt_and_user_authorization(self):
        kwargs = dict(remaining_budget=2, task_snapshot_current=True,
                      previous_attempt_preserved=True, new_attempt_identity=True,
                      explicit_retry_authorized=True)
        self.assertTrue(retry_decision("network_failure", **kwargs)["allowed"])
        self.assertTrue(retry_decision("model_timeout", **kwargs)["allowed"])
        for change in ({"remaining_budget":0}, {"remaining_budget":None},
                       {"task_snapshot_current":False}, {"previous_attempt_preserved":False},
                       {"new_attempt_identity":False}, {"explicit_retry_authorized":False}):
            values = {**kwargs, **change}
            self.assertFalse(retry_decision("network_failure", **values)["allowed"])
        self.assertFalse(retry_decision("budget_exhausted", **kwargs)["allowed"])
        self.assertFalse(retry_decision("academic_failure", **kwargs)["allowed"])
        exhausted = retry_decision("network_failure", **{**kwargs, "remaining_budget": 0})
        self.assertEqual(exhausted["disposition"], "terminate")
        for invalid_budget in (float("nan"), float("inf"), True):
            self.assertFalse(retry_decision("network_failure",
                **{**kwargs, "remaining_budget": invalid_budget})["allowed"])

    def test_i14_native_observation_preserves_original_error_and_known_context(self):
        message="network reset\\n"+"x"*1200
        row={"status":"technical_block","stage":"events","task_sha256":"a"*64,
             "executor":"codex_cli","failure_kind":"network_failure","error":message[:1000],
             "failure_evidence":{"raw_error":message}}
        value=attempt_observation(row)["failure_evidence"]
        self.assertEqual(value["raw_error"],message)
        self.assertEqual(value["stage"],"events")
        self.assertEqual(value["input_sha256"],"a"*64)
        self.assertEqual(value["executor"],"codex_cli")
        self.assertTrue(value["recovery_suggestion"])
        self.assertFalse(value["formal_eligible"])
        legacy=attempt_observation({"status":"failed","error":"network reset"})["failure_evidence"]
        self.assertEqual(legacy["outcome_kind"],"network_failure")
        self.assertIsNone(legacy["input_sha256"])
        self.assertIsNone(legacy["executor"])

    def test_i14_command_failure_does_not_invent_context(self):
        result={"status":"execution_failed","error":"network reset","stage":"events",
                "input_sha256":"not-a-hash"}
        value=command_observation("advance",result)["failure_evidence"]
        self.assertEqual(value["raw_error"],"network reset")
        self.assertEqual(value["stage"],"events")
        self.assertIsNone(value["input_sha256"])
        self.assertIsNone(value["executor"])
        self.assertIsNone(command_observation("prepare",{})["failure_evidence"])

    def test_cli_exit_zero_can_be_waiting(self):
        result={"action":"await_independent_review","status":"blocked_by_original_v3_gate"}
        output=io.StringIO()
        with patch.object(strict,"status",return_value=result),contextlib.redirect_stdout(output):
            self.assertEqual(strict.main(["advance","--run-id","fixture"]),0)
        body=json.loads(output.getvalue())
        self.assertEqual(body["runtime"]["runtime_status"],"waiting_for_review")
        self.assertFalse(body["runtime"]["academic_approval_granted"])


if __name__=="__main__": unittest.main()
