"""D18: fail closed at review intake; never synthesize a scholarly report."""
import hashlib
import json
from pathlib import Path
from review_execution import file_ref
from review_binding import audit_review_binding


def _persist_wait(run, reference, reason, detail, binding=None):
    record = {'schema_version': 1, 'task_snapshot': reference, 'status': 'unable_to_review',
              'reason_code': reason, 'detail': detail, 'candidate_binding': binding,
              'next_action': 'await_independent_review', 'advance_gate': False,
              'automatic_retry': False, 'independent_review_verified': False, 'formal_eligible': False}
    raw = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    root = Path(run).resolve(strict=True)
    folder = root / 'review_waiting'
    folder.mkdir(exist_ok=True)
    if folder.resolve() != folder or not folder.is_dir():
        raise ValueError('Waiting record directory is not owned by selected run')
    target = folder / (digest + '.json')
    try:
        with target.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        if target.is_symlink() or target.read_bytes() != raw:
            raise ValueError('Existing waiting record changed')
    return {**record, 'wait_ref': file_ref(root, target.relative_to(root).as_posix())}


def receive_review_or_wait(report_path, *, current_run_id, expected_reference, context_path,
                           expected_execution_ref=None, expected_identity_ref=None,
                           expected_isolation=None, launch_failure=None):
    """Caller supplies independently selected task and references. No legacy gate call.

    D16/D17 currently validate record consistency, not authentic independent access.
    Even a matched candidate must wait until a supported authorization path exists.
    """
    import task_packet
    # Never write a waiting record into a report-selected or superseded research run.
    task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    run = (task_packet.heritage.RUNS / current_run_id).resolve(strict=True)
    if launch_failure is not None:
        if not isinstance(launch_failure, str) or not launch_failure.strip():
            raise ValueError('Launch failure must have a concrete dispatcher reason')
        return _persist_wait(run, expected_reference, 'independent_session_unavailable', launch_failure[:1000])
    if any(x is None for x in (report_path, expected_execution_ref, expected_identity_ref, expected_isolation)):
        return _persist_wait(run, expected_reference, 'missing_independent_records',
                             'Report, execution, invocation and isolation references are required')
    try:
        bound = audit_review_binding(report_path, current_run_id=current_run_id,
                    expected_reference=expected_reference, context_path=context_path,
                    expected_execution_ref=expected_execution_ref, expected_identity_ref=expected_identity_ref,
                    expected_isolation=expected_isolation)
    except Exception as exc:
        # Failure stays outside legacy academic/revision history, no retry here.
        return _persist_wait(run, expected_reference, 'invalid_or_incomplete_records',
                             type(exc).__name__ + ': ' + str(exc)[:800])
    if bound.get('proposed_decision') == 'unable_to_review' or bound.get('execution_status') != 'completed':
        return _persist_wait(run, expected_reference, 'review_execution_incomplete',
                             'Execution or proposed review is incomplete', bound)
    return _persist_wait(run, expected_reference, 'independent_authorization_pending',
                         'Record matching alone cannot verify independent host access or authorize the original gate', bound)


def prepare_independent_wait(run_id):
    """E12: connect existing D21 preparation to D18, without launching a review."""
    from review_task import prepare_review_task
    candidate = prepare_review_task(run_id)
    wait = receive_review_or_wait(None, current_run_id=run_id,
        expected_reference=candidate["task_snapshot"], context_path=candidate["context_path"])
    return {"status":"blocked_by_original_v3_gate",
        "action":"await_independent_review","next":candidate["task_packet"]["stage_id"],
        "candidate":candidate,"wait":wait,"advance_gate":False,
        "automatic_retry":False,"formal_eligible":False}
