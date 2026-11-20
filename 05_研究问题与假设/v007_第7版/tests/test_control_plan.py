from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "04_议题文献与现实/v008_第8版/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from control_plan05 import BASELINE, audit_control_plan


class ControlPlanTests(unittest.TestCase):
    def test_literature_and_demographics_must_map_to_research_roles(self):
        evidence = {"E": {"paper_id": "P", "evidence_class": "direct", "document_id": "D"}}
        docs = {"D": {"kind": "fulltext"}}
        decisions = [{"concept": c, "label": c, "decision": "exclude", "causal_position": "not_applicable",
                      "reason": "TEST 不适用"} for c in BASELINE if c not in {"age", "sex"}]
        decisions += [
            {"concept": c, "label": c, "decision": "primary", "causal_position": "pre_exposure",
             "reason": "TEST 调整", "variable_id": c}
            for c in ["age", "sex"]]
        design = {"control_plan": {"unit": "individual", "unit_rationale": "TEST 个体",
                  "literature_models": [{"paper_id": "P", "evidence_id": "E", "table_or_section": "表2",
                                        "comparability": "同一结局", "controls": ["age", "sex"]}],
                  "decisions": decisions}}
        measured = {c: {"role": "control"} for c in ["age", "sex"]}
        errors = []
        audit_control_plan(design, measured, evidence, docs, errors)
        self.assertEqual(errors, [])
        design["control_plan"]["literature_models"][0]["controls"].append("parents_education")
        decisions.pop()
        docs["D"]["kind"] = "abstract"
        audit_control_plan(design, measured, evidence, docs, errors)
        self.assertTrue(any("缺少逐项审查: sex" in e for e in errors))
        self.assertTrue(any("尚无处置: parents_education" in e for e in errors))
        self.assertTrue(any("全文" in e for e in errors))
