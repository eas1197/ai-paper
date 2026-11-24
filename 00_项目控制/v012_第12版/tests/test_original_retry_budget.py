"""E26 original budget enforced even for retry; offline, no native launch."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import autopilot_v3 as auto

class OriginalRetryBudgetTest(unittest.TestCase):
    def test_budget_exhausted_before_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            auto.heritage.write(work/"v5_native_calls.json",{"records":[{"stage":"reality","status":"failed"}]*6})
            invoke=Mock()
            with patch.object(auto,"native_modules",return_value=(Mock(),invoke,Mock(),Mock())):
                with self.assertRaisesRegex(RuntimeError,"allowance exhausted"):
                    auto.Executor().call(work,"reality","fixture")
            invoke.assert_not_called()
    def test_requested_timeout_cannot_expand_original_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            invoke=Mock(side_effect=RuntimeError("Synthetic launch failure"))
            with patch.object(auto,"native_modules",return_value=(lambda:"fixture",invoke,Mock(),Mock())):
                with self.assertRaisesRegex(RuntimeError,"Synthetic"):
                    auto.Executor(timeout=99999).call(work,"reality","fixture")
            profile=auto.heritage.read(auto.heritage.CONTROL/"v007_第7版/dev_profile.json")
            self.assertEqual(invoke.call_args.kwargs["timeout"],profile["00"]["timeout_seconds"])
            self.assertEqual(auto.heritage.read(work/"v5_native_calls.json")["records"][0]["status"],"technical_block")

    def test_i03_failed_dispatch_preserves_observed_actions_and_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            def invoke(cli, attempt, *args, **kwargs):
                (attempt/"events.jsonl").write_text("fixture trace",encoding="utf-8")
                raise RuntimeError("Synthetic timeout")
            with patch.object(auto,"native_modules",return_value=(lambda:"fixture",invoke,lambda path:["a","b"],Mock())):
                with self.assertRaisesRegex(RuntimeError,"Synthetic timeout"):
                    auto.Executor().call(work,"reality","fixture")
            row=auto.heritage.read(work/"v5_native_calls.json")["records"][0]
            self.assertEqual(row["status"],"technical_block")
            self.assertEqual(row["model_call_reserved"],1)
            self.assertEqual(row["remaining_model_calls"],5)
            self.assertEqual(row["web_actions"],2)
            self.assertEqual(row["web_action_observation"],"observed_original_trace")
            self.assertEqual(row["events_sha256"],auto.checksum(work/"v5_native/reality/attempt_001/events.jsonl"))

    def test_i03_no_events_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            with patch.object(auto,"native_modules",return_value=(lambda:"fixture",Mock(return_value=1),Mock(),Mock())):
                with self.assertRaisesRegex(RuntimeError,"execution failed"):
                    auto.Executor().call(work,"reality","fixture")
            row=auto.heritage.read(work/"v5_native_calls.json")["records"][0]
            self.assertEqual(row["status"],"failed")
            self.assertIsNone(row["web_actions"])
            self.assertEqual(row["web_action_observation"],"missing_events")

    def test_i03_unreadable_response_preserves_failed_call(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            def invoke(cli, attempt, *args, **kwargs):
                (attempt/"events.jsonl").write_text('{"type":"thread.started","thread_id":"fixture"}',encoding="utf-8")
                (attempt/"response.json").write_text("not json",encoding="utf-8")
                return 0
            with patch.object(auto,"native_modules",return_value=(lambda:"fixture",invoke,lambda path:["a"],Mock())):
                with self.assertRaises(ValueError):
                    auto.Executor().call(work,"reality","fixture")
            row=auto.heritage.read(work/"v5_native_calls.json")["records"][0]
            self.assertEqual(row["status"],"failed")
            self.assertEqual(row["web_actions"],1)
            self.assertIsNotNone(row["response_sha256"])
