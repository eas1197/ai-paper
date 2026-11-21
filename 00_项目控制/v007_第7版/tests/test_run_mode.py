"""Exercise the experiment namespace and frozen allocation checks."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_mode


class ExperimentContract(unittest.TestCase):
    def test_budget_and_mode_are_bound_to_run_directory(self):
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as temp:
            with patch.object(run_mode, "RUNS", Path(temp)):
                work = run_mode.start("limits", "教育分流")
                manifest = run_mode.verified_run(work)
                self.assertEqual(manifest["workload"]["04"]["abstract_target"], 10)
                self.assertFalse(manifest["formal_eligible"])
                run_mode.enforce(work, "06", {"robustness_models": 1})
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    run_mode.enforce(work, "06", {"robustness_models": 2})
                with self.assertRaisesRegex(ValueError, "permission"):
                    run_mode.enforce(work, "09", {"send": True})
                moved = work.rename(work.with_name("other"))
                with self.assertRaisesRegex(ValueError, "Invalid or changed"):
                    run_mode.verified_run(moved)

    def test_rejects_changed_workload(self):
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as temp:
            with patch.object(run_mode, "RUNS", Path(temp)):
                work = run_mode.start("changed", "教育分流")
                path = work / "run_manifest.json"
                manifest = run_mode.load(path)
                manifest["workload"]["04"]["abstract_target"] = 2
                run_mode.write(path, manifest)
                with self.assertRaisesRegex(ValueError, "Invalid or changed"):
                    run_mode.verified_run(work)
