import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from stage06 import control_model_errors


class ControlModelTests(unittest.TestCase):
    def test_models_keep_primary_controls_and_comparisons_use_a_common_sample(self):
        plan = {"decisions": [{"variable_id": "age", "decision": "primary"},
                              {"variable_id": "sex", "decision": "primary"},
                              {"variable_id": "income", "decision": "sensitivity_only"}]}
        models = {"primary": {"analysis_role": "primary", "predictors": ["X", "age", "income"]},
                  "comparison": {"analysis_role": "robustness", "predictors": ["X", "age"], "control_comparison": True}}
        self.assertEqual(len(control_model_errors(plan, models, {"common_sample": False})), 3)
        models["primary"]["predictors"] = ["X", "age", "sex"]
        self.assertEqual(control_model_errors(plan, models, {"common_sample": True}), [])
        models["comparison"].pop("control_comparison")
        self.assertIn("sex", control_model_errors(plan, models, {"common_sample": True})[0])
