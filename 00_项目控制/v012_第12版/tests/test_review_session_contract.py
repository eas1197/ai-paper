import copy
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from review_session import validate_review_session_record, SCHEMA_PATH


def file_ref(path, char):
    return {"path": path, "sha256": char * 64}


def planned_record():
    return {
        "schema_version": 1,
        "task_snapshot": {
            "research_id": "R-1",
            "stage_id": "material_adequacy",
            "task_id": "REVIEW-1",
            "snapshot_sha256": "a" * 64,
        },
        "review_type": "academic_review",
        "review_kind": "material_adequacy",
        "launch_request": {
            "executor": "codex_cli",
            "mode": "ephemeral_process",
            "model": "gpt-6.2-sol",
            "model_source": "resume_writing.REVIEWER",
            "approval_policy": "never",
            "sandbox": "read-only",
            "ignore_user_config": True,
            "ephemeral": True,
            "skip_git_repo_check": True,
            "input_context": file_ref("review_task_context.json", "b"),
            "attempt_dir": "review_attempts/REVIEW-1/attempt_001",
            "input_scope": "frozen_task_snapshot_only",
            "write_scope": "attempt_directory_only",
            "external_search_allowed": False,
            "project_state_write_allowed": False,
            "gate_state_write_allowed": False,
        },
        "reviewer_identity": {
            "reviewer_id": "reviewer-openai-codex-01",
            "role": "independent_reviewer",
            "executor": "codex_cli",
            "provider": "OpenAI",
            "model": "gpt-6.2-sol",
            "invocation_id": "invocation-001",
            "primary_thread_id": "researcher-thread-01",
        },
        "role_isolation": {
            "separate_process_required": True,
            "ephemeral_thread_required": True,
            "same_session_roleplay_allowed": False,
            "researcher_hidden_context_included": False,
            "project_state_write_allowed": False,
            "gate_state_write_allowed": False,
            "external_search_allowed": False,
            "input_scope": "frozen_task_snapshot_only",
            "output_scope": "attempt_directory_only",
        },
        "session_record": {
            "execution_id": "execution-001",
            "status": "planned",
            "thread_id": None,
            "started_at": None,
            "finished_at": None,
            "events": None,
            "response": None,
            "login_probe": None,
            "execution_binding": None,
            "independence_status": "not_verified",
            "separation_status": "not_started",
            "failure_reason": None,
        },
    }


class ReviewSessionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_planned_ephemeral_codex_session_is_valid(self):
        record = planned_record()
        self.validator.validate(record)

    def test_planned_record_binds_snapshot_context_and_reviewer(self):
        record = planned_record()
        result = validate_review_session_record(
            record,
            record["task_snapshot"],
            record["launch_request"]["input_context"],
            record["reviewer_identity"],
            primary_thread_id="researcher-thread-01",
        )
        self.assertEqual(result["status"], "session_contract_matched")
        self.assertEqual(result["thread_separation"], "not_yet_started_or_completed")
        self.assertFalse(result["independent_review_verified"])
        self.assertFalse(result["formal_eligible"])

    def test_completed_record_is_only_a_distinct_thread_candidate(self):
        record = planned_record()
        record["session_record"].update({
            "status": "completed",
            "thread_id": "reviewer-thread-02",
            "started_at": "2026-11-24T10:00:00Z",
            "finished_at": "2026-11-24T10:02:00Z",
            "events": file_ref("attempt_001/events.jsonl", "c"),
            "response": file_ref("attempt_001/response.json", "d"),
            "login_probe": file_ref("attempt_001/login.json", "e"),
            "execution_binding": file_ref("attempt_001/execution_binding.json", "f"),
            "separation_status": "pending_verification",
        })
        result = validate_review_session_record(
            record,
            record["task_snapshot"],
            record["launch_request"]["input_context"],
            record["reviewer_identity"],
            primary_thread_id="researcher-thread-01",
        )
        self.assertEqual(result["thread_separation"], "distinct_thread_candidate_pending_authentication")
        self.assertEqual(result["identity_verification"], "pending_d17")
        self.assertFalse(result["independent_review_verified"])

    def test_same_thread_as_researcher_is_rejected(self):
        record = planned_record()
        record["session_record"].update({
            "status": "completed",
            "thread_id": "researcher-thread-01",
            "started_at": "2026-11-24T10:00:00Z",
            "finished_at": "2026-11-24T10:02:00Z",
            "events": file_ref("attempt_001/events.jsonl", "c"),
            "response": file_ref("attempt_001/response.json", "d"),
            "login_probe": file_ref("attempt_001/login.json", "e"),
            "execution_binding": file_ref("attempt_001/execution_binding.json", "f"),
            "separation_status": "pending_verification",
        })
        with self.assertRaisesRegex(ValueError, "reuses the primary"):
            validate_review_session_record(
                record,
                record["task_snapshot"],
                record["launch_request"]["input_context"],
                record["reviewer_identity"],
                primary_thread_id="researcher-thread-01",
            )

    def test_mismatched_snapshot_is_rejected(self):
        record = planned_record()
        expected = copy.deepcopy(record["task_snapshot"])
        expected["snapshot_sha256"] = "9" * 64
        with self.assertRaisesRegex(ValueError, "snapshot"):
            validate_review_session_record(record, expected, record["launch_request"]["input_context"], record["reviewer_identity"])

    def test_mismatched_context_hash_is_rejected(self):
        record = planned_record()
        expected = file_ref("review_task_context.json", "9")
        with self.assertRaisesRegex(ValueError, "context"):
            validate_review_session_record(record, record["task_snapshot"], expected, record["reviewer_identity"])

    def test_mismatched_reviewer_identity_is_rejected(self):
        record = planned_record()
        expected = copy.deepcopy(record["reviewer_identity"])
        expected["reviewer_id"] = "other-reviewer"
        with self.assertRaisesRegex(ValueError, "(?i)reviewer identity"):
            validate_review_session_record(record, record["task_snapshot"], record["launch_request"]["input_context"], expected)

    def test_primary_thread_must_match_dispatcher_selection(self):
        record = planned_record()
        with self.assertRaisesRegex(ValueError, "Primary researcher thread"):
            validate_review_session_record(record, record["task_snapshot"], record["launch_request"]["input_context"], record["reviewer_identity"], primary_thread_id="different-primary")

    def test_researcher_role_is_rejected(self):
        record = planned_record()
        record["reviewer_identity"]["role"] = "researcher"
        self.assertFalse(self.validator.is_valid(record))

    def test_writable_sandbox_is_rejected(self):
        record = planned_record()
        record["launch_request"]["sandbox"] = "workspace-write"
        self.assertFalse(self.validator.is_valid(record))

    def test_same_session_roleplay_is_rejected(self):
        record = planned_record()
        record["role_isolation"]["same_session_roleplay_allowed"] = True
        self.assertFalse(self.validator.is_valid(record))

    def test_hidden_researcher_context_is_rejected(self):
        record = planned_record()
        record["role_isolation"]["researcher_hidden_context_included"] = True
        self.assertFalse(self.validator.is_valid(record))

    def test_external_search_permission_is_rejected(self):
        record = planned_record()
        record["launch_request"]["external_search_allowed"] = True
        self.assertFalse(self.validator.is_valid(record))

    def test_project_or_gate_state_write_is_rejected(self):
        for field in ("project_state_write_allowed", "gate_state_write_allowed"):
            record = planned_record()
            record["role_isolation"][field] = True
            with self.subTest(field=field):
                self.assertFalse(self.validator.is_valid(record))

    def test_chatgpt_ui_is_not_misrepresented_as_supported_codex_launcher(self):
        record = planned_record()
        record["launch_request"]["executor"] = "chatgpt_ui"
        self.assertFalse(self.validator.is_valid(record))

    def test_completed_record_requires_native_thread_and_raw_records(self):
        record = planned_record()
        record["session_record"]["status"] = "completed"
        record["session_record"]["separation_status"] = "pending_verification"
        self.assertFalse(self.validator.is_valid(record))

    def test_d14_cannot_mark_independence_verified(self):
        record = planned_record()
        record["session_record"]["independence_status"] = "verified"
        self.assertFalse(self.validator.is_valid(record))

    def test_failed_or_unavailable_session_needs_reason(self):
        for status in ("failed", "unavailable"):
            record = planned_record()
            record["session_record"]["status"] = status
            with self.subTest(status=status):
                self.assertFalse(self.validator.is_valid(record))


if __name__ == "__main__":
    unittest.main()
