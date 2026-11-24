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
