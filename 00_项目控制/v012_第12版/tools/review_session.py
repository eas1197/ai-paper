"""Offline validation for the D14 independent-review session contract.

This validates the launch/identity record only. It does not start Codex, authenticate
a ChatGPT account, or certify that the reviewer is genuinely independent.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "review_session.schema.json"


def validate_review_session_record(
    record,
    expected_task_snapshot,
    expected_input_context,
    expected_reviewer_identity,
    primary_thread_id=None,
):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)

    if record["task_snapshot"] != expected_task_snapshot:
        raise ValueError("Review session task snapshot does not match the dispatcher-selected snapshot")
    if record["launch_request"]["input_context"] != expected_input_context:
        raise ValueError("Review session context path/hash does not match the frozen task context")
    if record["reviewer_identity"] != expected_reviewer_identity:
        raise ValueError("Reviewer identity does not match the dispatcher-selected reviewer")
    if record["reviewer_identity"]["model"] != record["launch_request"]["model"]:
        raise ValueError("Reviewer model differs between launch request and identity record")

    session = record["session_record"]
    if primary_thread_id is not None:
        if record["reviewer_identity"]["primary_thread_id"] != primary_thread_id:
            raise ValueError("Primary researcher thread does not match the dispatcher-selected thread")
        if session["thread_id"] is not None and session["thread_id"] == primary_thread_id:
            raise ValueError("Reviewer session reuses the primary researcher thread")

    if session["status"] == "completed" and primary_thread_id is None:
        separation = "pending_primary_thread_reference"
    elif session["status"] == "completed":
        separation = "distinct_thread_candidate_pending_authentication"
    else:
        separation = "not_yet_started_or_completed"

    return {
        "status": "session_contract_matched",
        "thread_separation": separation,
        "identity_verification": "pending_d17",
        "independent_review_verified": False,
        "formal_eligible": False,
    }
