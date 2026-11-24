"""D16: check invocation lineage from selected original records, not host attestation."""
import json
from pathlib import Path
from review_execution import load_ref, _timestamp


def audit_invocation(run, binding, identity_ref, *, allow_fixture=False):
    """Use D12 audit output and receiver-selected D15 reference, never model self-report."""
    identity = json.loads(load_ref(run, identity_ref))
    if identity.get('fixture') is not False and not (allow_fixture is True and identity.get('fixture') is True):
        raise ValueError('Fixture or unclassified execution is not a live credential')
    receipt = json.loads(load_ref(run, binding['execution_binding']))
    launch = json.loads(load_ref(run, identity['launch_ref']))
    runtime = json.loads(load_ref(run, identity['runtime_ref']))
    reviewer = binding['reviewer']
    if (binding['status'] != 'review_records_hash_bound_pending_independence'
            or receipt['task_snapshot'] != binding['task_snapshot']
            or receipt['reviewer'] != reviewer or receipt['execution_id'] != binding['execution_id']
            or any(x['task_snapshot'] != binding['task_snapshot'] or x['launch_id'] != binding['execution_id']
                   for x in (identity, launch, runtime))):
        raise ValueError('Invocation does not belong to selected task/launch')
    if any(x['executor'] != reviewer['executor'] for x in (identity, launch, runtime)):
        raise ValueError('Invocation executor mismatch')
    if reviewer['executor'] != 'codex_cli':
        raise ValueError('No authenticated independent host receipt adapter')
    if (identity['status'] != 'completed' or runtime['status'] != 'completed'
            or receipt['status'] != 'completed' or type(runtime['exit_code']) is not int
            or runtime['exit_code'] != 0 or identity['exit_code'] != 0
            or not identity['started_at'] or identity['started_at'] != _timestamp(runtime['started_at'])
            or identity['missing_or_issues']):
        raise ValueError('Incomplete or failed invocation')
    refs = {r['role']: {k: r[k] for k in ('path', 'sha256')} for r in receipt['records']}
    for role in ('events', 'response'):
        if not identity['records'][role] or refs.get(role) != identity['records'][role]:
            raise ValueError('Original invocation file mismatch')
    for ref in identity['records'].values():
        if ref is not None:
            load_ref(run, ref)
    parents = {Path(x['path']).parent for x in (identity_ref, identity['runtime_ref'], refs['events'], refs['response'])}
    if len(parents) != 1:
        raise ValueError('Cross-attempt invocation files')
    events = [json.loads(line) for line in load_ref(run, refs['events']).decode('utf-8-sig').splitlines()]
    starts = [e for e in events if e.get('type') == 'thread.started']
    completed = [e for e in events if e.get('type') == 'turn.completed']
    if (len(starts) != 1 or len(completed) != 1 or any(e.get('type') == 'turn.failed' for e in events)
            or not starts[0].get('thread_id') or starts[0]['thread_id'] != reviewer['invocation_id']
            or starts[0]['thread_id'] != identity['session_id']):
        raise ValueError('Missing, duplicate or mismatched native invocation')
    models = {e['model'] for e in events if e.get('type') in {'thread.started', 'turn.started', 'turn.completed'}
              and isinstance(e.get('model'), str) and e['model'].strip()}
    if models != {reviewer['model']} or identity['observed_model'] != reviewer['model'] or not reviewer['model']:
        raise ValueError('Actual model is absent or mismatched')
    response = json.loads(load_ref(run, refs['response']))
    report = json.loads(load_ref(run, receipt['report']))
    if response != report or report['reviewer'] != reviewer or report['task_snapshot'] != binding['task_snapshot']:
        raise ValueError('Native response differs from selected review report')
    return {'status': 'fixture_invocation_matched' if identity['fixture'] else 'native_invocation_matched_pending_independence',
            'identity_ref': identity_ref, 'session_id': identity['session_id'], 'fixture': identity['fixture'],
            'independent_review_verified': False, 'formal_eligible': False}
