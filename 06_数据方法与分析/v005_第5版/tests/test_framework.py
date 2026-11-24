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

    def test_duplicate_original_material_id_rejected(self):
        framework = dict.fromkeys(FRAMEWORK_CONTEXT, "fixture")
        framework["dimensions"] = [dict(id="d1",name="fixture",deduction="fixture",
            proposition="fixture",needed_material="fixture",relationship="fixture")]
        receipt = {"phase":"framework_collection","framework_sha256":digest(framework),
            "status":"pending_independent_review","materials":[{"material_id":"M"},{"material_id":"M"}]}
        with self.assertRaisesRegex(ValueError,"Duplicate or invalid"):
            analysis_matrix(framework,receipt,[])

    def test_native_action_and_source_fields_cannot_be_relabelled(self):
        framework = dict.fromkeys(FRAMEWORK_CONTEXT, "fixture")
        framework["dimensions"] = [dict(id="d1",name="fixture",deduction="fixture",
            proposition="fixture",needed_material="fixture",relationship="fixture")]
        receipt = {"phase":"framework_collection","framework_sha256":digest(framework),
            "status":"pending_independent_review","materials":[{"material_id":"M","url":"https://example.org",
            "locator":"fixture","kind":"actor_statement","event_id":"native-action-1"}]}
        base = dict(dimension_id="d1",status="tentative",conclusion="fixture",
            boundary="fixture",unresolved="fixture",alternatives="fixture")
        source={"material_id":"M","relation":"support","reason":"fixture"}
        result=analysis_matrix(framework,receipt,[dict(base,evidence=[source])])
        self.assertEqual(result["rows"][0]["evidence"][0]["event_id"],"native-action-1")
        for name,value in (("event_id","wrong"),("url","https://example.net"),("locator","wrong"),("kind","official_rule")):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,"source identity differs"):
                analysis_matrix(framework,receipt,[dict(base,evidence=[dict(source,**{name:value})])])
