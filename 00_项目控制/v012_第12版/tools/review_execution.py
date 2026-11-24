"""D15: preserve receiver-owned review attempt records, not authenticity or approval."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def file_ref(run, path):
    run = Path(run).resolve(strict=True)
    raw = str(path)
    rel = Path(raw)
    if rel.is_absolute() or '\\' in raw or ':' in raw or '..' in rel.parts:
        raise ValueError('Record path escapes run')
    resolved = (run / rel).resolve(strict=True)
    if not resolved.is_relative_to(run) or not resolved.is_file():
        raise ValueError('Invalid original record path')
    return {'path': rel.as_posix(), 'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest()}


def load_ref(run, ref):
    if file_ref(run, ref['path']) != ref:
        raise ValueError('Selected original record changed')
    return (Path(run) / ref['path']).read_bytes()


def _timestamp(value):
    if value is None:
        return None
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Execution timestamp must have a timezone')
    return date.astimezone(timezone.utc).isoformat()


def record_attempt(run, *, launch_ref, runtime_ref, attempt_dir, fixture=False):
    """Only the dispatcher supplies runtime_ref; never source it from model output.

    Runtime metadata is observed by the launching adapter, not the requested model.
    The function records bytes and missingness; D16-D20 verify provenance.
    """
    run = Path(run).resolve(strict=True)
    launch = json.loads(load_ref(run, launch_ref))
    runtime = json.loads(load_ref(run, runtime_ref))
    if runtime['launch_id'] != launch['launch_id'] or runtime['task_snapshot'] != launch['task_snapshot']:
        raise ValueError('Runtime belongs to a different launch or task')
    if runtime['executor'] != launch['executor']:
        raise ValueError('Runtime executor differs from launch')
    if runtime['status'] not in {'completed', 'failed', 'not_started'}:
        raise ValueError('Unknown runtime status')
    if type(fixture) is not bool:
        raise ValueError('Fixture flag must be explicit boolean')
    attempt = Path(attempt_dir)
    if attempt.is_absolute() or '..' in attempt.parts or '\\' in str(attempt) or ':' in str(attempt):
        raise ValueError('Attempt path escapes run')
    folder = (run / attempt).resolve(strict=True)
    if not folder.is_relative_to(run) or not folder.is_dir():
        raise ValueError('Invalid attempt directory')
    if (run / runtime_ref['path']).resolve().parent != folder:
        raise ValueError('Runtime metadata is not from the selected attempt')
    names = {'events': 'events.jsonl', 'response': 'response.json', 'stderr': 'stderr.log',
             'session_record': 'session_record.json'}
    records = {role: file_ref(run, (attempt / name).as_posix()) if (folder / name).exists() else None
               for role, name in names.items()}
    issues = []
    session = None
    model = None
    if runtime['executor'] == 'codex_cli' and records['events']:
        try:
            events = [json.loads(line) for line in load_ref(run, records['events']).decode('utf-8-sig').splitlines()]
            starts = [e for e in events if e.get('type') == 'thread.started']
            if len(starts) == 1 and isinstance(starts[0].get('thread_id'), str) and starts[0]['thread_id'].strip():
                session = starts[0]['thread_id']
            else:
                issues.append('missing_or_ambiguous_thread_started')
            # Only explicit native model metadata, never request/response guesses.
            models = {e['model'] for e in events if e.get('type') in {'thread.started', 'turn.started', 'turn.completed'}
                      and isinstance(e.get('model'), str) and e['model'].strip()}
            if len(models) == 1:
                model = models.pop()
            elif len(models) > 1:
                issues.append('ambiguous_observed_model')
        except (ValueError, AttributeError, TypeError):
            issues.append('malformed_events')
            session = model = None
    elif runtime['executor'] != 'codex_cli':
        # No host-authenticated Chat adapter exists yet; retain the raw file only.
        issues.append('host_session_authentication_pending')
    started_at = _timestamp(runtime.get('started_at'))
    if runtime['status'] == 'not_started' and started_at is not None:
        raise ValueError('Unstarted attempt cannot have a start time')
    if runtime['status'] == 'not_started':
        session = model = None
    for key, value in {'session_id': session, 'observed_model': model, 'started_at': started_at,
                       'response': records['response'], 'events': records['events']}.items():
        if value is None:
            issues.append('missing_' + key)
    if runtime['status'] != 'completed' or type(runtime.get('exit_code')) is not int or runtime['exit_code'] != 0:
        issues.append('execution_not_successful')
    record = {'schema_version': 1, 'launch_id': launch['launch_id'], 'task_snapshot': launch['task_snapshot'],
              'launch_ref': launch_ref, 'runtime_ref': runtime_ref, 'executor': runtime['executor'],
              'requested_model': launch.get('requested_model'), 'observed_model': model,
              'session_id': session, 'started_at': started_at, 'exit_code': runtime.get('exit_code'),
              'status': runtime['status'], 'records': records, 'missing_or_issues': sorted(set(issues)),
              'fixture': fixture, 'independent_review_verified': False, 'formal_eligible': False}
    target = folder / 'review_execution.json'
    raw = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    try:
        with target.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        if target.is_symlink() or not target.is_file() or target.read_bytes() != raw:
            raise FileExistsError('Existing review execution differs; preserve original record')
    return file_ref(run, (attempt / target.name).as_posix())
