import json
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_execution import record_attempt, file_ref, load_ref


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'attempt').mkdir()
        self.launch = {'launch_id': 'fixture-launch', 'task_snapshot': {'task_id': 'fixture'},
                       'executor': 'codex_cli', 'requested_model': 'requested'}
        self.runtime = {'launch_id': self.launch['launch_id'], 'task_snapshot': self.launch['task_snapshot'],
                        'executor': 'codex_cli', 'status': 'completed', 'exit_code': 0,
                        'started_at': '2026-01-01T08:00:00+08:00'}
        self.write('attempt/events.jsonl', {'type': 'thread.started', 'thread_id': 'fixture-thread', 'model': 'observed'})
        self.write('attempt/response.json', {'decision': 'pass', 'model': 'self-reported'})

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')
        return file_ref(self.root, name)

    def record(self, **kwargs):
        launch_ref = self.write('launch.json', self.launch)
        runtime_ref = self.write('attempt/runtime.json', self.runtime)
        args = dict(launch_ref=launch_ref, runtime_ref=runtime_ref, attempt_dir='attempt', fixture=True)
        args.update(kwargs)
        ref = record_attempt(self.root, **args)
        return json.loads(load_ref(self.root, ref))

    def test_records_real_fixture_bytes_not_approval(self):
        result = self.record()
        self.assertEqual(result['session_id'], 'fixture-thread')
        self.assertEqual(result['observed_model'], 'observed')
        self.assertEqual(result['started_at'], '2026-01-01T00:00:00+00:00')
        self.assertEqual(result['records']['response'], file_ref(self.root, 'attempt/response.json'))
        self.assertTrue(result['fixture'])
        self.assertFalse(result['formal_eligible'])
        self.assertFalse(result['independent_review_verified'])

    def test_missing_model_never_uses_request_or_response(self):
        self.write('attempt/events.jsonl', {'type': 'thread.started', 'thread_id': 'fixture-thread'})
        result = self.record()
        self.assertIsNone(result['observed_model'])
        self.assertIn('missing_observed_model', result['missing_or_issues'])

    def test_duplicate_session_is_ambiguous(self):
        path = self.root / 'attempt/events.jsonl'
        path.write_text(path.read_text() + '\n' + path.read_text())
        self.assertIsNone(self.record()['session_id'])

    def test_failure_without_events_or_response(self):
        self.runtime.update(status='failed', exit_code=1)
        (self.root / 'attempt/events.jsonl').unlink()
        (self.root / 'attempt/response.json').unlink()
        result = self.record()
        self.assertIn('execution_not_successful', result['missing_or_issues'])
        self.assertIsNone(result['records']['response'])

    def test_not_started_cannot_claim_start(self):
        self.runtime['status'] = 'not_started'
        with self.assertRaises(ValueError):
            self.record()

    def test_cross_task(self):
        self.runtime['task_snapshot'] = {'task_id': 'other'}
        with self.assertRaises(ValueError):
            self.record()

    def test_no_naive_time(self):
        self.runtime['started_at'] = '2026-01-01T00:00:00'
        with self.assertRaises(ValueError):
            self.record()

    def test_no_rewrite(self):
        self.record()
        with self.assertRaises(FileExistsError):
            self.record()

    def test_chat_no_host_authentication(self):
        self.launch['executor'] = self.runtime['executor'] = 'chat_native_web'
        self.write('attempt/session_record.json', {'session_id': 'self-reported'})
        result = self.record()
        self.assertIsNone(result['session_id'])
        self.assertIn('host_session_authentication_pending', result['missing_or_issues'])

    def test_tamper_reference(self):
        ref = self.write('launch.json', self.launch)
        self.write('launch.json', {'changed': True})
        with self.assertRaises(ValueError):
            load_ref(self.root, ref)

    def test_path_escape(self):
        with self.assertRaises(ValueError):
            self.record(attempt_dir='../attempt')


if __name__ == '__main__':
    unittest.main()
