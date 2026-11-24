"""C15: bind result files to the current task and independently selected records.

This receiver checks bytes and lineage, not authenticity of web events or academic
eligibility. C19–C24 will provide executor-specific provenance verification.
"""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

import task_packet

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/result_bundle.schema.json"


def _local_file(work, raw):
    if not isinstance(raw, str) or not raw:
        raise ValueError("Original record path must be explicit")
    path = Path(raw)
    if path.is_absolute() or "\\" in raw or ":" in raw or ".." in path.parts:
        raise ValueError("Original record path escapes run namespace")
    root = work.resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Missing or out-of-namespace original record: " + raw)
    return resolved


def _file_refs(provenance):
    kind = provenance["kind"]
    if kind == "chat_native_web":
        return [("chat_record", ref) for ref in provenance["record_refs"]]
    if kind == "manual":
        return [("manual_original", ref) for ref in provenance["original_files"]]
    return [(key, provenance[key]) for key in
            ("events", "response", "stderr", "prompt", "schema", "login")
            if provenance[key] is not None]


def _missing(provenance):
    missing = set(provenance["missing_fields"])
    kind = provenance["kind"]
    if kind == "chat_native_web" and not provenance["record_refs"]:
        missing.add("record_refs")
    elif kind == "manual":
        for key in ("submitter", "submitted_at", "original_files"):
            if not provenance[key]:
                missing.add(key)
    elif kind == "codex_cli":
        for key in ("command", "thread_id", "exit_code", "events", "response"):
            if provenance[key] is None:
                missing.add(key)
    return sorted(missing)


def audit_result_bundle(result_path, *, current_run_id, expected_reference,
                        expected_execution=None):
    """Read a run-relative result file and audit its binding.

    expected_execution is a separate receiver/dispatcher-owned record, selected
    independently of the submitted bundle. Never construct it from model claims.
    Missing independent binding remains pending even when claimed hashes match.
    No return value of this function grants formal academic eligibility.
    """
    if not isinstance(current_run_id, str):
        raise ValueError("Current run identity must be explicit")
    task_packet.heritage.run_id_guard(current_run_id)
    task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    path = _local_file(work, result_path)
    raw = path.read_bytes()
    bundle = json.loads(raw.decode("utf-8-sig"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise RuntimeError("Missing RFC3339 date-time validator")
    Draft202012Validator(schema, format_checker=checker).validate(bundle)
    task_packet.validate_result_snapshot(bundle, current_run_id=current_run_id,
                                         expected_reference=expected_reference)
    digest = hashlib.sha256(raw).hexdigest()
    provenance = bundle["provenance"]
    if expected_execution is not None:
        expected = {"task_snapshot": expected_reference, "executor": bundle["executor"],
                    "provenance": provenance, "result_sha256": digest}
        if expected_execution != expected:
            raise ValueError("Independent execution binding does not match result or task")
    checked = []
    seen = set()
    roles = {}
    for role, ref in _file_refs(provenance):
        original = _local_file(work, ref["path"])
        if original == path or original in seen:
            raise ValueError("Original records must be distinct from result and each other")
        actual = task_packet.heritage.sha(original)
        if actual != ref["sha256"]:
            raise ValueError("Original record hash mismatch: " + ref["path"])
        seen.add(original)
        roles[role] = original
        checked.append({"role": role, "path": ref["path"], "sha256": actual})
    if bundle["executor"] == "codex_cli" and "events" in roles and "response" in roles:
        if roles["events"].parent != roles["response"].parent:
            raise ValueError("Codex events and response belong to different attempts")
    missing = _missing(provenance)
    # Execution outcome is a separate declaration, never an eligibility verdict.
    if bundle["execution_status"] == "failed":
        status = "execution_failed"
    elif missing:
        status = "pending_missing_original_records"
    elif expected_execution is None:
        status = "pending_independent_execution_binding"
    elif bundle["executor"] == "codex_cli" and provenance["exit_code"] != 0:
        status = "execution_failed"
    else:
        status = "records_hash_bound_pending_source_verification"
    return {"task_snapshot": expected_reference, "executor": bundle["executor"],
            "result_path": result_path, "result_sha256": digest, "checked_files": checked,
            "missing_fields": missing, "status": status,
            "execution_status": bundle["execution_status"],
            "execution_issues": bundle["execution_issues"],
            "independent_binding_matched": expected_execution is not None,
            "formal_eligible": False}
