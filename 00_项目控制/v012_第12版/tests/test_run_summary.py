import contextlib
import io
import json
import unittest
from unittest.mock import patch
from test_advance_trace import AdvanceTraceTests as fixture
import ai_paper5_strict as strict
from advance_trace import observe_advance
from run_summary import export_summary


class RunSummaryTests(unittest.TestCase):
    setUp=fixture.setUp

    def test_i20_cli_exports_same_manifest_and_summary_without_replay(self):
        observe_advance("fixture","strict_progress",lambda:{"status":"blocked_by_original_v3_gate"})
        with patch.object(strict,"original_call") as original, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(strict.main(["run-summary","--run-id","fixture"]),0)
            original.assert_not_called()
        result=json.loads(output.getvalue())["result"]
        manifest=strict.read(self.work/result["manifest"]["path"])
        summary=(self.work/result["summary"]["path"]).read_text()
        self.assertEqual(manifest["counts"]["original_progress_dispatches"],1)
        self.assertIn("原推进派发：1",summary)
        self.assertFalse(manifest["new_execution_performed"])
        self.assertEqual(result,export_summary("fixture"))
        self.assertFalse((self.work/"runtime_log").exists())

    def test_i20_tamper_and_interruption_are_not_success(self):
        observe_advance("fixture","autopilot_step",lambda:{})
        trace=next((self.work/"advance_trace").iterdir())
        (trace/"finish.json").unlink()
        bad=self.work/"runtime_log"
        bad.mkdir()
        strict.write(bad/("a"*64+".json"),{"research_id":"other"})
        result=export_summary("fixture")
        manifest=strict.read(self.work/result["manifest"]["path"])
        self.assertEqual(manifest["counts"]["command_records"],0)
        self.assertEqual(manifest["counts"]["unresolved_records"],1)
        self.assertEqual(manifest["counts"]["incomplete_or_invalid_traces"],1)
        self.assertIsNone(manifest["advance_observations"][0]["stage_changed"])
        self.assertFalse(manifest["formal_eligible"])

    def test_i20_wrong_run_identity_blocks_export(self):
        strict.write(self.work/"run_manifest.json",{"run_id":"other"})
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            export_summary("fixture")
        self.assertFalse((self.work/"run_summaries").exists())


if __name__=="__main__":
    unittest.main()
