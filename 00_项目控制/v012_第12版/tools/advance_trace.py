"""I19: record real scheduler attempts before and after original gate execution."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from run_observation import classify_failure
from runtime_log import _ref

TRIGGERS = {"autopilot_step", "strict_progress"}
REVIEW_OUTCOMES = {"pass","academic_pass","missing_data","materials_pending",
                   "concept","value","depth","increment","technical"}


def _state_view(work, run_id):
    path = work / "staged_topic.json"
    if path.is_symlink():
        raise ValueError("Original state path is symlinked")
    raw = path.read_bytes()
    state = json.loads(raw.decode("utf-8-sig"))
    if state.get("run_id") != run_id or state.get("mode") != "dev":
        raise ValueError("Original state identity mismatch")
    history = state.get("history", [])
    last = history[-1].get("outcome") if history and isinstance(history[-1], dict) else None
    return {
        "stage": state.get("status"), "state_sha256": hashlib.sha256(raw).hexdigest(),
        "last_original_review_outcome": last if last in REVIEW_OUTCOMES else None,
        "original_gate_state": "observed_original_stage_only",
        "user_hold": _ref(work, "runtime_user_holds/active.json"),
        "user_cancel": _ref(work, "runtime_user_holds/cancelled.json"),
        "academic_approval_granted": False
    }


def _open_trace(run_id, trigger):
    import task_packet
    h = task_packet.heritage
    if trigger not in TRIGGERS:
        raise ValueError("Unknown automatic progression trigger")
    h.run_id_guard(run_id)
    root = h.RUNS.resolve()
    candidate = root / run_id
    # The original entry still owns init/identity checks. Do not invent a run.
    if not (candidate/"run_manifest.json").is_file() or not (candidate/"staged_topic.json").is_file():
        return None
    work = candidate.resolve(strict=True)
    if work.parent != root or work.name != run_id:
        raise ValueError("Progress trace escapes original run")
    manifest = task_packet.run_mode.verified_run(work)
    if manifest.get("run_id") != run_id:
        raise ValueError("Progress trace run mismatch")
    before = _state_view(work, run_id)
    folder = work / "advance_trace"
    if folder.is_symlink():
        raise ValueError("Progress trace directory is symlinked")
    folder.mkdir(exist_ok=True)
    if folder.resolve() != folder:
        raise ValueError("Progress trace directory escapes original run")
    trace_id = uuid4().hex
    attempt = folder / trace_id
    attempt.mkdir(exist_ok=False)
    start = {"schema_version":1,"trace_id":trace_id,"research_id":run_id,
             "trigger":trigger,"scope":"scheduler_iteration" if trigger=="autopilot_step" else "original_progress_dispatch",
             "before":before,"observed_at":datetime.now(timezone.utc).isoformat(),
             "gate_authority":"original_v009_and_original_module","formal_eligible":False}
    _write_once(attempt/"start.json",start)
    return work, attempt, start


def _write_once(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _finish(trace, result=None, error=None):
    if trace is None:
        return
    work, attempt, start = trace
    try:
        after = _state_view(work,start["research_id"])
    except (OSError,ValueError,TypeError,KeyError):
        after = None
    view = result if isinstance(result,dict) else {}
    # Do not persist raw error strings, arbitrary reports, or source payloads.
    def tag(name):
        item = view.get(name)
        return item if isinstance(item,str) and len(item)<=100 and all(
            c.isalnum() or c in "_-" for c in item) else None
    finish = {"schema_version":1,"trace_id":start["trace_id"],"research_id":start["research_id"],
              "start_ref":_ref(work,attempt/"start.json"),
              "after":after,"stage_changed":(start["before"]["stage"]!=after["stage"]) if after else None,
              "observed_at":datetime.now(timezone.utc).isoformat(),
              "result_action":tag("action"),"result_status":tag("status"),"result_next":tag("next"),
              "exception_kind":classify_failure(error) if error is not None else None,
              "exception_sha256":hashlib.sha256(str(error).encode()).hexdigest() if error is not None else None,
              "command_returned":error is None,"formal_eligible":False,"academic_approval_granted":False}
    _write_once(attempt/"finish.json",finish)


def observe_advance(run_id, trigger, invoke):
    """Record pre-dispatch state before original action; never grant a gate or retry."""
    trace = _open_trace(run_id, trigger)
    try:
        result = invoke()
    except Exception as error:
        _finish(trace,error=error)
        raise
    _finish(trace,result=result)
    return result
