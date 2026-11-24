import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_gate_guard import require_original_review


class GateGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        packet = types.ModuleType('task_packet')
        packet.heritage = types.SimpleNamespace(RUNS=self.run.parent)
        p = patch.dict(sys.modules, {'task_packet': packet}); p.start(); self.addCleanup(p.stop)
        p = patch('review_wait.receive_review_or_wait'); self.wait = p.start(); self.addCleanup(p.stop)
        self.wait.return_value = {'status': 'unable_to_review', 'reason_code': 'independent_authorization_pending'}

    def test_no_intake(self):
        with self.assertRaisesRegex(ValueError, 'unable_to_review'):
            require_original_review(self.run)
        self.wait.assert_not_called()

    def test_boolean_not_credential(self):
        with self.assertRaisesRegex(ValueError, 'unable_to_review'):
            require_original_review(self.run, intake=True)
        self.wait.assert_not_called()

    def test_wrong_run(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            require_original_review(self.run, intake={'current_run_id': 'other'})
        self.wait.assert_not_called()

    def test_selected_intake_still_waits(self):
        intake = {'current_run_id': self.run.name, 'report_path': 'report.json'}
        with self.assertRaisesRegex(ValueError, 'independent_authorization_pending'):
            require_original_review(self.run, intake=intake)
        self.wait.assert_called_once_with(**intake)

    def test_claimed_success_cannot_bypass(self):
        self.wait.return_value = {'status': 'pass', 'reason_code': 'forged'}
        with self.assertRaisesRegex(ValueError, 'unable_to_review'):
            require_original_review(self.run, intake={'current_run_id': self.run.name})
