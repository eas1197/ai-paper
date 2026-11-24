"""E24: exact completed call reuse and conflict preservation."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import autopilot_v3 as auto
import ai_paper5_strict as strict
sys.path.insert(0,str(strict.V32/"tools"))
from staged_topic import write_stage_once

class RepeatedDispatchTest(unittest.TestCase):
    def test_reuse_does_not_reserve_another_call(self):
        engine=Mock()
        saved=({"sources":[]},Path("attempt"),"fixture",[{"id":"fixture"}],None)
        with patch.object(auto,"completed_call",return_value=saved):
            self.assertIs(auto.call_once(engine,Path("unused"),"reality","same",must_search=True),saved)
        engine.call.assert_not_called()

    def test_changed_completed_call_stops_without_reexecution(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            strict.write(work/"v5_native_calls.json",{"records":[{"stage":"issue","status":"completed"}]})
            engine=Mock()
            with patch.object(auto,"completed_call",return_value=None):
                with self.assertRaisesRegex(ValueError,"Preserve completed call"):
                    auto.call_once(engine,work,"issue","changed")
            engine.call.assert_not_called()

    def test_stage_product_never_overwritten_on_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"reality.json"
            write_stage_once(path,{"fixture":True})
            before=path.read_bytes()
            write_stage_once(path,{"fixture":True})
            with self.assertRaisesRegex(ValueError,"Preserve existing"):
                write_stage_once(path,{"fixture":False})
            self.assertEqual(path.read_bytes(),before)
