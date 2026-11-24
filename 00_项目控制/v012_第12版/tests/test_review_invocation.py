import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_execution import file_ref, record_attempt
from review_invocation import audit_invocation


class InvocationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        (self.run / 'attempt').mkdir()
        self.snapshot = {'research_id': 'fixture', 'stage_id': 's', 'task_id': 't', 'snapshot_sha256': 'a'*64}
        self.launch = {'launch_id': 'attempt-1', 'task_snapshot': self.snapshot, 'executor': 'codex_cli', 'requested_model': 'm'}
        self.runtime = dict(self.launch, status='completed', exit_code=0, started_at='2026-01-01T00:00:00Z')
        self.reviewer = {'executor': 'codex_cli', 'model': 'm', 'invocation_id': 'thread-1', 'reviewer_id': 'fixture-reviewer'}
        self.report = {'reviewer': self.reviewer, 'task_snapshot': self.snapshot, 'decision': 'pass'}
        self.events = [{'type': 'thread.started', 'thread_id': 'thread-1', 'model': 'm'}, {'type': 'turn.completed'}]

    def write(self, name, data):
        (self.run / name).write_text(json.dumps(data), encoding='utf-8')
        return file_ref(self.run, name)

    def setup_records(self):
        lr = self.write('launch.json', self.launch)
        rr = self.write('attempt/runtime.json', self.runtime)
        (self.run / 'attempt/events.jsonl').write_text('\n'.join(map(json.dumps, self.events)), encoding='utf-8')
        response = self.write('attempt/response.json', self.report)
        self.identity = record_attempt(self.run, launch_ref=lr, runtime_ref=rr, attempt_dir='attempt', fixture=True)
        self.receipt = {'task_snapshot': self.snapshot, 'reviewer': self.reviewer, 'execution_id': 'attempt-1', 'status': 'completed',
                        'report': self.write('report.json', self.report), 'records': [{'role': 'events', **file_ref(self.run, 'attempt/events.jsonl')}, {'role': 'response', **response}]}
        self.binding = {'status': 'review_records_hash_bound_pending_independence', 'task_snapshot': self.snapshot, 'reviewer': self.reviewer,
                        'execution_id': 'attempt-1', 'execution_binding': self.write('receipt.json', self.receipt)}

    def check(self, **kw):
        return audit_invocation(self.run, self.binding, self.identity, **kw)

    def test_fixture_never_live(self):
        self.setup_records()
        with self.assertRaises(ValueError): self.check()
        result = self.check(allow_fixture=True)
        self.assertEqual(result['status'], 'fixture_invocation_matched')
        self.assertFalse(result['formal_eligible'])

    def test_duplicate_thread(self):
        self.events.insert(0, self.events[0])
        self.setup_records()
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_missing_completed(self):
        self.events.pop()
        self.setup_records()
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_wrong_invocation(self):
        self.reviewer['invocation_id'] = 'wrong'
        self.setup_records()
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_wrong_model(self):
        self.reviewer['model'] = 'wrong'
        self.setup_records()
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_changed_events(self):
        self.setup_records()
        (self.run / 'attempt/events.jsonl').write_text('{}')
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_changed_response(self):
        self.setup_records()
        (self.run / 'attempt/response.json').write_text('{}')
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_cross_task(self):
        self.setup_records()
        self.binding['task_snapshot'] = dict(self.snapshot, task_id='other')
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_chat_not_authenticated(self):
        self.launch['executor'] = self.runtime['executor'] = self.reviewer['executor'] = 'chat_native_web'
        self.setup_records()
        with self.assertRaises(ValueError): self.check(allow_fixture=True)

    def test_mismatched_report(self):
        self.setup_records()
        self.receipt['report'] = self.write('report.json', dict(self.report, decision='reject'))
        self.binding['execution_binding'] = self.write('receipt.json', self.receipt)
        with self.assertRaises(ValueError): self.check(allow_fixture=True)
