import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_paper5_strict as strict
import task_packet
import autopilot_v3
from advance_trace import observe_advance


class AdvanceTraceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.work=self.root/"fixture"
        self.work.mkdir()
        strict.write(self.work/"run_manifest.json",{"run_id":"fixture"})
        self.state={"run_id":"fixture","mode":"dev","status":"initial","history":[]}
        strict.write(self.work/"staged_topic.json",self.state)
        for mock in (patch.object(strict,"RUNS",self.root),
                     patch.object(task_packet.run_mode,"verified_run",return_value={"run_id":"fixture"})):
            mock.start()
            self.addCleanup(mock.stop)

    def entries(self):
        return sorted((self.work/"advance_trace").glob("*/start.json"))

    def test_i19_original_transition_records_pre_state_before_dispatch(self):
        before=strict.sha(self.work/"staged_topic.json")
        def original(*args,**kwargs):
            self.assertEqual(len(self.entries()),1)
            self.assertEqual(strict.read(self.entries()[0])["before"]["state_sha256"],before)
            strict.write(self.work/"staged_topic.json",dict(self.state,status="preliminary_review"))
            return "{}"
        with patch.object(strict,"doctor"),patch.object(strict,"codex_task",return_value={"task_snapshot":{}}), \
             patch.object(strict,"original_call",side_effect=original):
            result=strict.status("fixture",progress=True)
        start=strict.read(self.entries()[0])
        finish=strict.read(self.entries()[0].parent/"finish.json")
        self.assertEqual(result["after"],"preliminary_review")
        self.assertEqual(start["trigger"],"strict_progress")
        self.assertEqual(start["before"]["stage"],"initial")
        self.assertTrue(finish["stage_changed"])
        self.assertEqual(finish["after"]["stage"],"preliminary_review")
        self.assertFalse(finish["academic_approval_granted"])

    def test_i19_failed_attempt_keeps_start_and_failure_without_raw_error(self):
        with patch.object(autopilot_v3,"_step",side_effect=RuntimeError("private fixture error")):
            with self.assertRaisesRegex(RuntimeError,"private fixture"):
                autopilot_v3.step("fixture")
        start=self.entries()[0]
        finish=strict.read(start.parent/"finish.json")
        self.assertEqual(strict.read(start)["trigger"],"autopilot_step")
        self.assertEqual(finish["exception_kind"],"technical_failure")
        self.assertFalse(finish["command_returned"])
        self.assertFalse(finish["stage_changed"])
        self.assertNotIn("private fixture error",json.dumps(finish))

    def test_i19_identical_waits_are_distinct_and_status_query_does_not_write(self):
        for _ in range(2):
            observe_advance("fixture","strict_progress",lambda:{"status":"blocked_by_original_v3_gate"})
        self.assertEqual(len(self.entries()),2)
        for start in self.entries():
            self.assertFalse(strict.read(start.parent/"finish.json")["stage_changed"])
        with patch.object(strict,"doctor"):
            strict.status("fixture",progress=False)
        self.assertEqual(len(self.entries()),2)


if __name__=="__main__":
    unittest.main()
