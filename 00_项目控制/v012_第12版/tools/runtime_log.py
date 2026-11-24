"""I18: content-addressed command observations, not a second academic ledger."""
import hashlib
import json
from pathlib import Path

from review_execution import file_ref

READ_ONLY = frozenset({"status", "prepare", "commands", "doctor", "review-counts"})
INPUT_ARGS = ("report", "task", "result", "execution_binding", "observed_actions",
              "conversion", "review", "matrix", "framework", "framework_revision",
              "input", "packet", "manuscript", "claims", "events_jsonl",
              "prior_report", "revision_record", "selection", "aliases", "user_decision_file")
CONTEXT_FILES = {
    "identity": ("run_manifest.json", "staged_topic.json"),
    "source": ("reality.json", "event_comparison.json", "merged_literature.json",
               "initial/literature_matrix.json", "supplemental/literature_matrix.json"),
    "budget": ("v5_native_calls.json", "initial/checkpoint.json", "supplemental/checkpoint.json"),
    "review": ("matrix_independent_review.json", "autonomous_writing_status.json"),
    "revision": ("autonomous_writing/revision_checkpoint.json",),
}


def _ref(work, path):
    """Only local run-owned files, never absolute external paths or contents."""
    if path is None:
        return None
    try:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = work / candidate
        if candidate.is_symlink():
            return None
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(work) or not resolved.is_file():
            return None
        return file_ref(work, resolved.relative_to(work).as_posix())
    except (OSError, ValueError, TypeError, RuntimeError):
        return None


def _argument_ref(work, path, *, output=False):
    # argparse Path values and CLI output paths are relative to the process CWD.
    # String input references in receivers are relative to the selected run.
    if path is None:
        return None
    return _ref(work, Path(path).absolute() if isinstance(path, Path) or output else path)


def _snapshot(work, run_id, result):
    import task_packet
    view = result.get("result", result) if isinstance(result, dict) else {}
    candidate = view.get("candidate", view) if isinstance(view, dict) else {}
    ref = candidate.get("task_snapshot") if isinstance(candidate, dict) else None
    if ref is None:
        return None, "not_supplied", None
    try:
        snapshot = task_packet.verify_snapshot(ref, current_run_id=run_id)
        return ref, "current_verified", snapshot["packet"]
    except Exception:
        # Failed or stale references must not acquire the authority of a current task.
        return None, "unverified_or_stale", None


def record_command(args, result, runtime, *, success):
    """Record the observed command, not an inferred model launch or review pass."""
    command = args.cmd
    if command in READ_ONLY:
        return {"recording_status": "read_only"}
    run_id = getattr(args, "run_id", None)
    if run_id is None:
        return {"recording_status": "unbound_no_explicit_run"}
    import task_packet
    h = task_packet.heritage
    try:
        h.run_id_guard(run_id)
        root = h.RUNS.resolve(strict=True)
        work = (root / run_id).resolve(strict=True)
        if work.parent != root or work.name != run_id:
            return {"recording_status": "unbound_invalid_run"}
        manifest = task_packet.run_mode.verified_run(work)
        state = h.state_of(run_id)
        if manifest.get("run_id") != run_id or state.get("run_id") != run_id:
            return {"recording_status": "unbound_invalid_run"}
    except Exception:
        return {"recording_status": "unbound_invalid_run"}
    ref, ref_status, packet = _snapshot(work, run_id, result)
    contexts = {key: [item for name in names if (item := _ref(work, name)) is not None]
                for key, names in CONTEXT_FILES.items()}
    # Record only supplied run-local input paths or frozen inputs, not external path strings.
    inputs = {name: item for name in INPUT_ARGS
              if (item := _argument_ref(work, getattr(args, name, None))) is not None}
    outputs = {name: item for name in ("output", "task_output")
               if success and (item := _argument_ref(work, getattr(args, name, None), output=True)) is not None}
    if packet is not None:
        inputs["frozen_inputs"] = packet["input_files"]
    exception = runtime.get("outcome_kind")
    evidence = runtime.get("failure_evidence")
    error_hash = None
    if isinstance(evidence, dict) and isinstance(evidence.get("raw_error"), str):
        error_hash = hashlib.sha256(evidence["raw_error"].encode("utf-8")).hexdigest()
    record = {
        "schema_version": 1, "record_kind": "command_observation",
        "research_id": run_id, "stage_id": state.get("status"),
        "command": command, "task_id": ref["task_id"] if ref else None,
        "task_snapshot": ref, "task_snapshot_status": ref_status,
        "executor": "v012_router", "execution_executor": None,
        "model_requested": getattr(args, "model", None), "model_observed": None,
        "inputs": inputs, "outputs": outputs, "sources": contexts["source"],
        "original_identity_refs": contexts["identity"],
        "budget": {"frozen_quantity": packet.get("quantity_budget") if packet else None,
                   "frozen_time_seconds": packet.get("time_budget_seconds") if packet else None,
                   "original_ledger_refs": contexts["budget"], "actual_consumption": None},
        "review": {"original_refs": contexts["review"], "independent_verified": False},
        "revision": {"original_refs": contexts["revision"], "actual_rounds": None},
        "exception": {"outcome_kind": exception, "raw_error_sha256": error_hash} if exception else None,
        "command_success": success, "runtime_status": runtime.get("runtime_status"),
        "started_at": None, "finished_at": None, "formal_eligible": False,
        "academic_approval_granted": False, "complete_history_guaranteed": False,
        "record_scope": "command boundary; original receipts remain authoritative"
    }
    raw = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
    folder = work / "runtime_log"
    if folder.is_symlink():
        raise ValueError("Runtime log directory is symlinked")
    folder.mkdir(exist_ok=True)
    if folder.resolve() != folder:
        raise ValueError("Runtime log directory escapes run")
    target = folder / (hashlib.sha256(raw).hexdigest()+".json")
    if target.is_symlink():
        raise ValueError("Runtime log entry is symlinked")
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if not target.is_file() or target.read_bytes() != raw:
            raise ValueError("Runtime log entry content mismatch")
    return {"recording_status": "recorded", "record_ref": file_ref(work, target.relative_to(work))}


def attach_command_record(args, result, runtime, *, success):
    """Observation failures are explicit, never academic outcomes or silent deletion."""
    try:
        return record_command(args, result, runtime, success=success)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return {"recording_status": "record_failed", "formal_eligible": False}
