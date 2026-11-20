"""Reuse the 04 workflow fixture with the new G5 evidence and review contract."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "04_议题文献与现实/v007_第7版/tests"))
import test_workflow as fixtures

rt = fixtures.rt
stage05 = fixtures.s5


class QuestionWorkflowTests(fixtures.WorkflowTests):
    def fixture05(self, upstream):
        inputs, annotations, path = super().fixture05(upstream)
        library = rt.load(stage05.plan(inputs)["question_library"]["path"])
        annotations["significance_reviews"] = [{
            "candidate_id": "CAND_TEST", "decision": "pass", "reason": "TEST审查依据",
            "reviewer": "TEST_reviewer", "reviewed_at": fixtures.STAMP,
            "dimensions": {
                "reality": {"status": "supported", "assessment": "TEST现象", "population": "TEST群体",
                            "observation": "TEST观测", "baseline": "TEST基线", "scope": "TEST时点", "evidence_ids": ["E_news"]},
                "theory": {"status": "supported", "assessment": "TEST理论", "existing_explanation": "TEST既有解释",
                           "unresolved_prediction": "TEST待区分预测", "contribution": "TEST适用条件", "evidence_ids": ["E_FULL_0"]},
                "practice": {"status": "supported", "assessment": "TEST实践", "user": "TEST实施者",
                             "decision": "TEST行动", "consequence": "TEST后果", "evidence_ids": ["E_FULL_0"]},
                "policy": {"status": "supported", "assessment": "TEST政策", "policy_objective": "TEST目标",
                           "implementation_problem": "TEST执行取舍", "decision": "TEST政策判断",
                           "boundary": "TEST范围", "evidence_ids": ["E_policy"]},
            },
            "answer_use": {
                "simpler_question": "TEST总体情况", "added_information": "TEST比较两类差异",
                "evidence_needed": "TEST同一指标比较和区间", "expected_answer": "TEST预期方向",
                "if_expected": "TEST定向调整", "competing_answer": "TEST相反方向",
                "if_competing": "TEST重核解释", "if_negligible": "TEST维持原方案",
                "if_inconclusive": "TEST补样本提高精度",
            },
            "example_transfers": [{"paper_id": library["cases"][-1]["paper_id"], "borrowed_move": "TEST动作",
                                   "adaptation": "TEST变成比较", "scope_limit": "TEST边界"}],
        }]
        rt.write(path, annotations)
        return inputs, annotations, path

    def test_incomplete_meaning_and_same_answers_cannot_freeze(self):
        first = self.passed04()
        inputs, annotations, path = self.fixture05(first)
        review = annotations["significance_reviews"][0]
        review["dimensions"]["policy"]["evidence_ids"] = ["E_FULL_0"]
        review["answer_use"]["if_competing"] = review["answer_use"]["if_expected"]
        rt.write(path, annotations)
        result = stage05.execute(stage05.plan(inputs, self.config()))
        report = rt.load(Path(result["attempt_path"]) / "gate_report.json")
        self.assertEqual(report["significance_review_counts"]["pass"], 0)
        self.assertTrue(any("政策原文证据" in error for error in report["errors"]))
        self.assertTrue(any("区分两种答案的用途" in error for error in report["errors"]))
        self.assertFalse(rt.load(Path(result["attempt_path"]) / "analysis_design.json")["frozen"])

    def test_retrieval_and_model_tasks_run_in_order(self):
        first = fixtures.s4.execute(fixtures.s4.plan(self.inputs("04"), self.config()))
        inputs = self.inputs("05", upstream=str(Path(first["attempt_path"]) / "stage_manifest.json"))
        calls = []

        class Model:
            provider_id = "test"
            model_version = "fixture"

            def propose(self, payload):
                calls.append(payload)
                return {"test_task": payload["task_id"]}

        result = stage05.execute(stage05.plan(inputs, self.config()), {"model_provider": Model()})
        self.assertEqual(result["status"], "needs_review")
        work = Path(result["attempt_path"])
        examples = rt.load(work / "question_learning.json")["examples"]
        self.assertEqual(len({r["journal"] for r in examples}), 5)
        self.assertEqual(calls[0]["task_id"], "learn_framing")
        self.assertEqual(calls[1]["framing_proposal"]["test_task"], "learn_framing")
        audit = next(row for row in calls if row["task_id"] == "question_significance")
        self.assertEqual(len(audit["candidate_proposals"]), 4)
        self.assertEqual(calls[-1]["significance_proposal"]["test_task"], "question_significance")
        self.assertTrue(all(r["review_status"] == "unverified" for r in rt.load(work / "model_proposals.json")))


if __name__ == "__main__":
    unittest.main()
