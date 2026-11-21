"""Replay joint 04/05 tests using a fixture that meets current G5 inputs."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "04_议题文献与现实/v008_第8版/tests/test_workflow.py"


def install_fixture(module):
    original = module.WorkflowTests.fixture05

    def current_definition(test, upstream):
        inputs, annotations, path = original(test, upstream)
        design = annotations["analysis_design"]
        design["evidence_requirements"] = "TEST 同期变量与研究对象支持关联估计。"
        design["primary_method_rationale"] = "TEST 线性模型对应连续结局的条件均值之差。"
        concepts = ("age", "sex", "education", "marital_status", "residence", "hukou", "employment", "economic_resources")
        design["control_plan"] = {"unit": "individual", "unit_rationale": "TEST 问卷记录以个人为单位。",
                                  "literature_models": [{"paper_id": "P_TEST_000", "evidence_id": "E_FULL_0",
                                                         "table_or_section": "TEST模型说明", "comparability": "TEST同期个体关联",
                                                         "controls": ["age", "sex"]}],
                                  "decisions": [{"concept": key, "label": key, "decision": "unavailable",
                                                 "causal_position": "not_applicable", "reason": "TEST问卷仅含 X/Y",
                                                 "baseline_exception": "TEST固定的两题夹具未抽取人口学字段"} for key in concepts]}
        module.rt.write(path, annotations)
        return inputs, annotations, path

    module.WorkflowTests.fixture05 = current_definition


def main():
    spec = importlib.util.spec_from_file_location("topic_fixture04", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    install_fixture(module)
    if sys.argv[1:] == ["--stage06"]:
        original = importlib.util.spec_from_file_location

        def current_spec(name, location, *args, **kwargs):
            if Path(location).name == "test_workflow.py":
                return spec
            return original(name, location, *args, **kwargs)

        original_exec = spec.loader.exec_module

        def load_with_current_inputs(target):
            original_exec(target)
            install_fixture(target)

        spec.loader.exec_module = load_with_current_inputs
        with patch.object(importlib.util, "spec_from_file_location", side_effect=current_spec):
            tests = unittest.defaultTestLoader.discover(str(ROOT / "06_数据方法与分析/v004_第4版/tests"))
            return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1
    tests = unittest.defaultTestLoader.loadTestsFromModule(module)
    return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
