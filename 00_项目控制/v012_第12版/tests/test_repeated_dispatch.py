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

    def test_i07_native_attempt_identity_and_repeated_completed_result(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            def invoke(cli, attempt, *args, **kwargs):
                (attempt/"events.jsonl").write_text(json.dumps({"type":"thread.started","thread_id":"fixture"})+"\n",encoding="utf-8")
                strict.write(attempt/"response.json",{"fixture":True})
                return 0
            native=(lambda:"fixture",Mock(side_effect=invoke),lambda path:["fixture"],None)
            with patch.object(auto,"native_modules",return_value=native):
                engine=auto.Executor()
                first=auto.call_once(engine,work,"reality","same",must_search=True)
                second=auto.call_once(engine,work,"reality","same",must_search=True)
                self.assertEqual(first,second)
                native[1].assert_called_once()
                history=work/"v5_native_calls.json"
                ledger=strict.read(history)
                self.assertEqual(len(ledger["records"]),1)
                row=ledger["records"][0]
                self.assertEqual(row["task_sha256"],auto.checksum(first[1]/"task.json"))
                self.assertEqual(row["execution_task_id"],auto.execution_task_id(work,"reality",1,row["task_sha256"]))
                self.assertNotEqual(row["execution_task_id"],auto.execution_task_id(work,"reality",2,row["task_sha256"]))
                self.assertNotEqual(row["execution_task_id"],auto.execution_task_id(work,"issue",1,row["task_sha256"]))
                row["execution_task_id"]="tampered"
                strict.write(history,ledger)
                with self.assertRaisesRegex(ValueError,"Preserve completed call"):
                    auto.call_once(engine,work,"reality","same",must_search=True)
                native[1].assert_called_once()
