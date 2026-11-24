import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_wait import receive_review_or_wait
from review_execution import load_ref


class WaitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.ref = {'research_id': self.run.name, 'stage_id': 's', 'task_id': 't', 'snapshot_sha256': 'a'*64}
        self.packet = types.ModuleType('task_packet')
        self.packet.heritage = types.SimpleNamespace(RUNS=self.run.parent)
        self.packet.verify_snapshot = Mock(return_value={})
        p = patch.dict(sys.modules, {'task_packet': self.packet}); p.start(); self.addCleanup(p.stop)
        p = patch('review_wait.audit_review_binding'); self.audit = p.start(); self.addCleanup(p.stop)
        self.audit.return_value = {'proposed_decision': 'pass', 'execution_status': 'completed', 'formal_eligible': False}
        self.args = dict(current_run_id=self.run.name, expected_reference=self.ref, context_path='ctx.json',
                         expected_execution_ref={}, expected_identity_ref={}, expected_isolation={})

    def receive(self, **changes):
        return receive_review_or_wait('report.json', **dict(self.args, **changes))

    def check_wait(self, result):
        self.assertEqual(result['status'], 'unable_to_review')
        self.assertFalse(result['advance_gate'])
        self.assertFalse(result['automatic_retry'])
        self.assertFalse(result['formal_eligible'])
        load_ref(self.run, result['wait_ref'])

    def test_no_session(self):
        r = self.receive(launch_failure='no authenticated session available')
        self.check_wait(r); self.audit.assert_not_called()
        self.assertEqual(r['reason_code'], 'independent_session_unavailable')

    def test_missing_each_record(self):
        for name in ('expected_execution_ref', 'expected_identity_ref', 'expected_isolation'):
            with self.subTest(name=name):
                self.check_wait(self.receive(**{name: None}))
        self.audit.assert_not_called()

    def test_bad_or_duplicate_identity(self):
        self.audit.side_effect = ValueError('Reviewer reuses researcher thread')
        r = self.receive(); self.check_wait(r)
        self.assertEqual(r['reason_code'], 'invalid_or_incomplete_records')
        self.audit.assert_called_once()

    def test_fixture_rejected(self):
        self.audit.side_effect = ValueError('Fixture is not live credential')
        self.check_wait(self.receive())

    def test_failed_review(self):
        self.audit.return_value['execution_status'] = 'failed'
        r = self.receive(); self.check_wait(r)
        self.assertEqual(r['reason_code'], 'review_execution_incomplete')

    def test_matched_candidate_is_not_approval(self):
        r = self.receive(); self.check_wait(r)
        self.assertEqual(r['reason_code'], 'independent_authorization_pending')

    def test_same_failure_idempotent(self):
        one = self.receive(launch_failure='no session')
        two = self.receive(launch_failure='no session')
        self.assertEqual(one['wait_ref'], two['wait_ref'])
        self.assertEqual(len(list((self.run / 'review_waiting').iterdir())), 1)

    def test_stale_snapshot_never_writes(self):
        self.packet.verify_snapshot.side_effect = ValueError('Superseded snapshot')
        with self.assertRaises(ValueError): self.receive()
        self.assertFalse((self.run / 'review_waiting').exists())
