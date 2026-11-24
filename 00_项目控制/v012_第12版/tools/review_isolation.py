"""D17: verify distinct native threads and exact, independently frozen review input."""
import json
from pathlib import Path
from review_execution import load_ref


INSTRUCTION = 'Review only the submitted frozen materials. Do not use hidden context, extra files, or search. Return the required review result; do not authorize a formal gate.'


def isolated_request(run, snapshot, context_ref, permitted_inputs, frozen_inputs):
    frozen = {row['path']: row['sha256'] for row in frozen_inputs}
    refs = [context_ref, *permitted_inputs]
    if len({r['path'] for r in refs}) != len(refs) or any(frozen.get(r['path']) != r['sha256'] for r in refs):
        raise ValueError('Review input is duplicate or not in selected frozen task')
    context = json.loads(load_ref(run, context_ref))
    materials = [{**r, 'content': load_ref(run, r).decode('utf-8-sig')} for r in permitted_inputs]
    return {'instruction': INSTRUCTION, 'task_snapshot': snapshot, 'context': context, 'materials': materials}


def audit_isolation(run, invocation, *, snapshot, context_ref, permitted_inputs,
                    frozen_inputs, researcher_event_refs, allow_fixture=False):
    if invocation.get('status') not in {'native_invocation_matched_pending_independence', 'fixture_invocation_matched'}:
        raise ValueError('No matched invocation to isolate')
    if invocation.get('fixture') is not False and not (allow_fixture is True and invocation.get('fixture') is True):
        raise ValueError('Fixture is not a live isolation receipt')
    identity = json.loads(load_ref(run, invocation['identity_ref']))
    launch = json.loads(load_ref(run, identity['launch_ref']))
    runtime = json.loads(load_ref(run, identity['runtime_ref']))
    if identity['task_snapshot'] != snapshot or identity['session_id'] != invocation['session_id']:
        raise ValueError('Selected isolation task or thread changed')
    if (launch.get('session_policy') != 'new_isolated_session' or launch.get('context_ref') != context_ref
            or launch.get('permitted_inputs') != permitted_inputs
            or launch.get('researcher_event_refs') != researcher_event_refs):
        raise ValueError('Launch is not the independently selected isolated request')
    if not researcher_event_refs or len({r['path'] for r in researcher_event_refs}) != len(researcher_event_refs):
        raise ValueError('Missing or duplicate researcher event references')
    threads = []
    for ref in researcher_event_refs:
        events = [json.loads(line) for line in load_ref(run, ref).decode('utf-8-sig').splitlines()]
        starts = [row.get('thread_id') for row in events if row.get('type') == 'thread.started']
        if len(starts) != 1 or not isinstance(starts[0], str) or not starts[0].strip():
            raise ValueError('Researcher thread is missing or ambiguous')
        threads.append(starts[0])
    if invocation['session_id'] in threads or len(set(threads)) != len(threads):
        raise ValueError('Reviewer reuses researcher thread or researcher records are duplicated')
    stdin_ref = runtime.get('stdin_ref')
    if not stdin_ref or Path(stdin_ref['path']).parent != Path(identity['runtime_ref']['path']).parent:
        raise ValueError('Missing same-attempt captured reviewer input')
    submitted = json.loads(load_ref(run, stdin_ref))
    expected = isolated_request(run, snapshot, context_ref, permitted_inputs, frozen_inputs)
    if submitted != expected:
        raise ValueError('Reviewer input contains omitted, changed, or non-whitelisted content')
    return {'status': 'fixture_isolation_matched' if identity['fixture'] else 'input_and_threads_matched_pending_host_isolation',
            'researcher_threads': threads, 'reviewer_thread': identity['session_id'], 'stdin_ref': stdin_ref,
            'fixture': identity['fixture'], 'independent_review_verified': False, 'formal_eligible': False}
