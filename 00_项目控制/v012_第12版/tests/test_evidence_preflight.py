"""E23: never spend a new model call on missing or changed source receipts."""
import shutil
import unittest
import uuid
from unittest.mock import Mock
import ai_paper5_strict as strict
import task_packet
from autopilot_v3 import step

class EvidencePreflightTest(unittest.TestCase):
    def setUp(self):
        self.run="e23_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run,theme="Offline fixture"))
        self.state=strict.state_of(self.run)
        reality={"phenomenon":"fixture","search_focus":"fixture","sources":[]}
        strict.write(self.work/"reality.json",reality)
        self.state.update(status="explanation_exchange",reality_sha256=task_packet._digest(reality))
        strict.write(self.work/"staged_topic.json",self.state)

    def test_missing_original_reality_stops_before_event_search(self):
        (self.work/"reality.json").unlink()
        engine=Mock()
        with self.assertRaises(OSError): step(self.run,executor=engine)
        engine.call.assert_not_called()

    def test_incomplete_saved_event_receipt_stops_before_model(self):
        strict.write(self.work/"event_comparison.json",{"run_id":self.run,
            "reality_sha256":self.state["reality_sha256"],"event_count":2})
        engine=Mock()
        with self.assertRaisesRegex(ValueError,"receipts incomplete"):
            step(self.run,executor=engine)
        engine.call.assert_not_called()

    def test_changed_reality_stops_before_event_search(self):
        strict.write(self.work/"reality.json",{"phenomenon":"changed"})
        engine=Mock()
        with self.assertRaisesRegex(ValueError,"Reality evidence changed"):
            step(self.run,executor=engine)
        engine.call.assert_not_called()
