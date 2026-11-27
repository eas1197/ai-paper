from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from qual_materials import digest
from framework import FRAMEWORK_CONTEXT, analysis_matrix, validate_framework


class FrameworkTest(unittest.TestCase):
    def test_flow_labels_without_theoretical_reasoning_do_not_define_framework(self):
        with self.assertRaisesRegex(ValueError, "research reasoning"):
            validate_framework({"dimensions": [{"id": "apply", "name": "Apply"}]})

    def test_requires_bound_material_and_retains_negative_evidence(self):
        dimension = dict(id="proof", name="Proof", deduction="Theory", proposition="Prediction",
                         needed_material="Rule and exception", relationship="Conditions of use")
        framework = dict.fromkeys(FRAMEWORK_CONTEXT, "fixture")
        framework["dimensions"] = [dimension]
        receipt = {"phase": "framework_collection", "framework_sha256": digest(framework),
                   "status": "pending_independent_review", "materials": [
                       {"material_id": "M", "url": "https://example.org", "locator": "rule 1",
                        "kind": "official_rule"}]}
        finding = dict(dimension_id="proof", status="tentative", conclusion="Limited",
                       boundary="One case", unresolved="Enforcement unknown", alternatives="Discretion",
                       evidence=[{"material_id": "M", "relation": "counterexample", "reason": "Competing rule"}])
        matrix = analysis_matrix(framework, receipt, [finding])
        self.assertEqual(matrix["rows"][0]["evidence"][0]["relation"], "counterexample")
        self.assertEqual(matrix["theoretical_increment_status"], "proposed")
        with self.assertRaisesRegex(ValueError, "unresolved"):
            analysis_matrix(framework, receipt, [dict(finding, evidence=[])])
