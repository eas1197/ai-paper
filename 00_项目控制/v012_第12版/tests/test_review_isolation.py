import json
import unittest
import test_review_invocation
from review_invocation import audit_invocation
from review_isolation import isolated_request, audit_isolation


class IsolationTest(unittest.TestCase):
    setUp = test_review_invocation.InvocationTest.setUp
    write = test_review_invocation.InvocationTest.write
    setup_records = test_review_invocation.InvocationTest.setup_records

    def prepare(self, *, duplicate=False, hidden=False, unfrozen=False, no_input=False, old_launch=False):
        ctx = self.write('context.json', {'research_question': 'fixture'})
        artifact = self.write('material.json', {'submitted': 'evidence'})
        research = self.write('research_events.jsonl', {'type': 'thread.started', 'thread_id': 'thread-1' if duplicate else 'research-1'})
        self.args = dict(snapshot=self.snapshot, context_ref=ctx, permitted_inputs=[artifact],
                         frozen_inputs=[ctx, artifact], researcher_event_refs=[research], allow_fixture=True)
        self.launch.update(session_policy='resume' if old_launch else 'new_isolated_session', context_ref=ctx,
                           permitted_inputs=[artifact], researcher_event_refs=[research])
        prompt = isolated_request(self.run, self.snapshot, ctx, [artifact], [ctx, artifact])
        if hidden:
            prompt['hidden_conclusion'] = 'not submitted'
        if not no_input:
            self.runtime['stdin_ref'] = self.write('attempt/stdin.json', prompt)
        if unfrozen:
            self.args['frozen_inputs'] = [ctx]
        self.setup_records()
        self.invocation = audit_invocation(self.run, self.binding, self.identity, allow_fixture=True)

    def audit(self):
        return audit_isolation(self.run, self.invocation, **self.args)

    def test_distinct_and_exact(self):
        self.prepare()
        result = self.audit()
        self.assertEqual(result['status'], 'fixture_isolation_matched')
        self.assertFalse(result['independent_review_verified'])

    def test_same_thread(self):
        self.prepare(duplicate=True)
        with self.assertRaises(ValueError): self.audit()

    def test_hidden_conclusion(self):
        self.prepare(hidden=True)
        with self.assertRaises(ValueError): self.audit()

    def test_unfrozen_input(self):
        self.prepare(unfrozen=True)
        with self.assertRaises(ValueError): self.audit()

    def test_missing_stdin(self):
        self.prepare(no_input=True)
        with self.assertRaises(ValueError): self.audit()

    def test_resume_rejected(self):
        self.prepare(old_launch=True)
        with self.assertRaises(ValueError): self.audit()

    def test_changed_material(self):
        self.prepare()
        self.write('material.json', {'submitted': 'changed'})
        with self.assertRaises(ValueError): self.audit()

    def test_fixture_rejected_by_default(self):
        self.prepare()
        del self.args['allow_fixture']
        with self.assertRaises(ValueError): self.audit()
