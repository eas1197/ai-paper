import contextlib
import io
import json
import unittest
from unittest.mock import patch
import ai_paper5_strict as strict
import autopilot_v3


class UnifiedEntrypointTests(unittest.TestCase):
    def invoke(self,args):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            code=strict.main(args)
        return code,json.loads(stream.getvalue())

    def test_discovery_is_read_only_and_complete(self):
        with patch.object(strict,"doctor") as doctor, patch.object(strict,"original_call") as original:
            code,body=self.invoke(["commands"])
        self.assertEqual(code,0)
        self.assertEqual(len(body["result"]["commands"]),26)
        self.assertIn("run-summary",body["result"]["commands"])
        self.assertTrue({"init","status","advance","review","materials","quantitative-plan","resume-writing","writer4","prepare","autopilot","commands"} <= set(body["result"]["commands"]))
        doctor.assert_not_called()
        original.assert_not_called()

    def test_prepare_delegates_exact_original(self):
        with patch.object(strict,"doctor"),patch.object(strict,"original_call",return_value='{"status":"reality"}') as original:
            code,body=self.invoke(["prepare","--run-id","fixture"])
        self.assertEqual(code,0)
        self.assertEqual(body["result"]["status"],"reality")
        original.assert_called_once_with(strict.original_command("prepare","fixture"))

    def test_autopilot_delegates_and_preserves_blocked_status(self):
        expected={"status":"checkpoint","result":{"status":"blocked_by_original_v3_gate"},"formal_eligible":False}
        with patch.object(autopilot_v3,"run_autopilot",return_value=expected) as run:
            code,body=self.invoke(["autopilot","--run-id","fixture","--theme","fixture","--timeout","30","--max-steps","2"])
        self.assertEqual(code,0)
        self.assertEqual(body["result"],expected)
        run.assert_called_once_with("fixture",theme="fixture",model=None,timeout=30,max_steps=2)

    def test_autopilot_failure_is_not_success(self):
        with patch.object(autopilot_v3,"run_autopilot",side_effect=RuntimeError("original blocked")):
            code,body=self.invoke(["autopilot","--run-id","fixture"])
        self.assertEqual(code,2)
        self.assertEqual(body["status"],"blocked")


if __name__=="__main__": unittest.main()
