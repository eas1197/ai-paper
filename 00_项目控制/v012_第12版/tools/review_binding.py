"""D12: bind a proposed review to the independently selected task and execution records."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from review_evidence import SCHEMA, audit_review_evidence


def _local_file(run, raw):
    # Same namespace restrictions as C04/C15; never resolve a report-selected run.
    if not isinstance(raw, str) or not raw:
        raise ValueError("Record path must be explicit")
    rel = Path(raw)
    if rel.is_absolute() or "\\" in raw or ":" in raw or ".." in rel.parts:
        raise ValueError("Record path escapes run")
    path = (run / rel).resolve(strict=True)
    if not path.is_relative_to(run) or not path.is_file():
        raise ValueError("Missing or out-of-run record")
    return path


def _read_bound(run, ref):
    path = _local_file(run, ref["path"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Selected record bytes changed")
    return path, raw


def audit_review_binding(report_path, *, current_run_id, expected_reference,
                         context_path, expected_execution_ref=None):
    """The receiver selects context and receipt independently; no identity authentication here."""
    import task_packet

    # C04 owns version validity, run ownership, dependency invalidation and input hashes.
    snapshot = task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    run = (task_packet.heritage.RUNS / current_run_id).resolve(strict=True)
    path = _local_file(run, report_path)
    raw = path.read_bytes()
    report = json.loads(raw.decode("utf-8-sig"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)
    if report["task_snapshot"] != expected_reference:
        raise ValueError("Review does not belong to the selected task snapshot")
    packet = snapshot["packet"]
    inputs = {item["path"]: item["sha256"] for item in packet["input_files"]}
    if context_path not in inputs:
        raise ValueError("Selected review context is not in the frozen task")
    context_file, context_raw = _read_bound(run, {"path": context_path, "sha256": inputs[context_path]})
    context = json.loads(context_raw.decode("utf-8-sig"))
    if context["research_question"] != packet["research_question"]:
        raise ValueError("Review context question differs from frozen task")
    if any(inputs.get(item["path"]) != item["sha256"] for item in context["input_materials"]):
        raise ValueError("Review artifact is not in the frozen task")
    evidence = audit_review_evidence(run, context, report)
    result = {"task_snapshot": expected_reference, "report_sha256": hashlib.sha256(raw).hexdigest(),
              "proposed_decision": report["decision"], "evidence": evidence,
              "formal_eligible": False, "independent_review_verified": False}
    if expected_execution_ref is None:
        if report["decision"] != "unable_to_review":
            raise ValueError("Missing independently selected execution binding")
        return {**result, "status": "pending_missing_execution_binding"}
    # Receipt is created outside the model response, after execution. No circular hashes.
    Draft202012Validator(schema["$defs"]["file_ref"]).validate(expected_execution_ref)
    receipt_path, receipt_raw = _read_bound(run, expected_execution_ref)
    receipt = json.loads(receipt_raw.decode("utf-8-sig"))
    Draft202012Validator({"$schema": schema["$schema"], "$defs": schema["$defs"],
                          "$ref": "#/$defs/execution_binding"}).validate(receipt)
    if (receipt["task_snapshot"] != expected_reference or receipt["reviewer"] != report["reviewer"]
            or receipt["execution_id"] != report["execution_id"]
            or receipt["report"] != {"path": report_path, "sha256": result["report_sha256"]}):
        raise ValueError("Execution binding differs from selected review/task/identity")
    if receipt_path in {path, context_file}:
        raise ValueError("Execution receipt must be distinct from review and context")
    if receipt["status"] != "completed" and report["decision"] != "unable_to_review":
        raise ValueError("Failed execution cannot submit a completed review decision")
    roles, seen = {}, {path, context_file, receipt_path}
    for record in receipt["records"]:
        original, _ = _read_bound(run, record)
        if original in seen or record["role"] in roles:
            raise ValueError("Duplicate or self-referenced execution record")
        seen.add(original)
        roles[record["role"]] = original
    executor = receipt["reviewer"]["executor"]
    required = {"codex_cli": {"events", "response"}, "chat_native_web": {"session_record"},
                "manual": {"manual_record"}}[executor]
    if receipt["status"] == "completed" and not required <= roles.keys():
        raise ValueError("Missing executor-specific original records")
    if "events" in roles and "response" in roles and roles["events"].parent != roles["response"].parent:
        raise ValueError("Events and response are from different attempts")
    return {**result, "status": "review_records_hash_bound_pending_independence",
            "execution_id": receipt["execution_id"], "reviewer": receipt["reviewer"],
            "execution_status": receipt["status"], "execution_binding": expected_execution_ref}
