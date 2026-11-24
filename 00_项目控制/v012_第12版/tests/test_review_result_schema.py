import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "review_result.schema.json"


def evidence_ref(relation="supports"):
    return {
        "evidence_ref_id": "ER-1",
        "evidence_id": "MAT-01",
        "artifact_id": "qualitative-material-receipt",
        "path": "qualitative_framework/attempt_001/material_receipt.json",
        "sha256": "a" * 64,
        "locator": {"type": "record_id", "value": "MAT-01 / event-17"},
        "relation": relation,
        "claim_ids": ["CL-1"],
        "dimension_ids": ["DIM-1"],
        "support_scope": "只支持该访谈对象在该情境下的行动描述，不支持总体频率或因果结论",
        "limitations": ["单一来源，不能外推总体"],
        "verification_status": "verified_in_snapshot",
    }


def counterexample(status="not_found_after_review", refs=None):
    return {
        "status": status,
        "evidence_ref_ids": list(refs or []),
        "search_scope": "已核对当前冻结材料包中与该主张直接相关的来源及反例字段",
    }


def base_result():
    ref = evidence_ref()
    return {
        "schema_version": 2,
        "task_snapshot": {
            "research_id": "research-001",
            "stage_id": "empirical_matrix",
            "task_id": "review-task-001",
            "snapshot_sha256": "b" * 64,
        },
        "review_kind": "empirical_matrix",
        "decision": "pass",
        "reason": "逐维度核对了冻结材料、主张支持范围和反例",
        "issues": [],
        "assessment_scope": "只审查当前冻结矩阵，不对未提交的其他材料作推断",
        "evidence_references": [ref],
        "claim_assessments": [{
            "claim_id": "CL-1",
            "assessment": "supported",
            "evidence_ref_ids": ["ER-1"],
            "counterexample_check": counterexample(),
            "support_scope": "仅支持单个案例中的过程描述",
            "unresolved_question_ids": [],
        }],
        "dimension_assessments": [{
            "dimension_id": "DIM-1",
            "assessment": "supported",
            "evidence_ref_ids": ["ER-1"],
            "counterexample_check": counterexample(),
            "support_scope": "该维度有一项可定位材料支持，仍受单一案例范围限制",
            "unresolved_question_ids": [],
        }],
        "unresolved_questions": [],
    }


class ReviewResultSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def valid(self, result):
        return self.validator.is_valid(result)

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_pass_requires_file_bound_evidence_and_scope(self):
        self.assertTrue(self.valid(base_result()))

    def test_missing_evidence_reference_array_is_rejected(self):
        result = base_result()
        del result["evidence_references"]
        self.assertFalse(self.valid(result))

    def test_evidence_requires_artifact_path_hash_and_locator(self):
        for field in ("artifact_id", "path", "sha256", "locator", "support_scope"):
            result = base_result()
            del result["evidence_references"][0][field]
            with self.subTest(field=field):
                self.assertFalse(self.valid(result))

    def test_bad_hash_is_rejected(self):
        result = base_result()
        result["evidence_references"][0]["sha256"] = "not-a-sha"
        self.assertFalse(self.valid(result))

    def test_absolute_or_parent_path_is_rejected(self):
        for path in ("/tmp/source.json", "../source.json", "a/../../source.json"):
            result = base_result()
            result["evidence_references"][0]["path"] = path
            with self.subTest(path=path):
                self.assertFalse(self.valid(result))

    def test_missing_counterexample_check_is_rejected(self):
        result = base_result()
        del result["claim_assessments"][0]["counterexample_check"]
        self.assertFalse(self.valid(result))

    def test_found_counterexample_requires_a_specific_reference(self):
        result = base_result()
        result["claim_assessments"][0]["counterexample_check"] = counterexample("found")
        self.assertFalse(self.valid(result))

    def test_counterexample_reference_must_be_verified_in_snapshot(self):
        result = base_result()
        result["evidence_references"].append(evidence_ref("counterexample") | {
            "evidence_ref_id": "ER-2",
            "evidence_id": "MAT-02",
            "locator": {"type": "page", "value": "p. 12, para. 3"},
        })
        result["claim_assessments"][0]["counterexample_check"] = counterexample("found", ["ER-2"])
        result["dimension_assessments"][0]["counterexample_check"] = counterexample("found", ["ER-2"])
        self.assertTrue(self.valid(result))

    def test_unverified_or_changed_file_cannot_be_cited_as_evidence(self):
        result = base_result()
        result["evidence_references"][0]["verification_status"] = "hash_mismatch"
        self.assertFalse(self.valid(result))

    def test_pass_cannot_hide_blocking_unresolved_question(self):
        result = base_result()
        result["unresolved_questions"] = [{
            "question_id": "U-1",
            "claim_ids": ["CL-1"],
            "dimension_ids": ["DIM-1"],
            "question": "该机制是否在其他案例中同样出现？",
            "reason": "当前材料只有一个案例",
            "needed_evidence": "至少一个独立案例及其原始材料",
            "blocking": True,
        }]
        result["claim_assessments"][0]["unresolved_question_ids"] = ["U-1"]
        result["dimension_assessments"][0]["unresolved_question_ids"] = ["U-1"]
        self.assertFalse(self.valid(result))

    def test_pass_cannot_contain_unsupported_claim(self):
        result = base_result()
        result["claim_assessments"][0]["assessment"] = "unsupported"
        self.assertFalse(self.valid(result))

    def test_pass_cannot_leave_counterexamples_unassessed(self):
        result = base_result()
        result["claim_assessments"][0]["counterexample_check"] = counterexample("not_assessed")
        self.assertFalse(self.valid(result))

    def test_need_evidence_requires_gap_and_unresolved_question(self):
        result = base_result()
        result["decision"] = "need_evidence"
        result["issues"] = [{
            "issue_id": "I-1",
            "dimension_id": "DIM-1",
            "category": "evidence_gap",
            "blocking": True,
            "detail": "当前没有可定位材料支持该主张",
            "evidence_ids": [],
            "evidence_ref_ids": [],
            "counterexample_ref_ids": [],
            "unresolved_question_ids": ["U-1"],
            "required_action": "补充独立来源或将主张降格",
        }]
        result["evidence_references"] = []
        result["claim_assessments"][0].update(
            assessment="not_assessed",
            evidence_ref_ids=[],
            counterexample_check=counterexample("not_assessed"),
            unresolved_question_ids=["U-1"],
        )
        result["dimension_assessments"][0].update(
            assessment="unresolved",
            evidence_ref_ids=[],
            counterexample_check=counterexample("not_assessed"),
            unresolved_question_ids=["U-1"],
        )
        result["unresolved_questions"] = [{
            "question_id": "U-1",
            "claim_ids": ["CL-1"],
            "dimension_ids": ["DIM-1"],
            "question": "哪项独立材料可以支持该主张？",
            "reason": "现有输入没有相应材料",
            "needed_evidence": "可定位的独立来源及其原始文件",
            "blocking": True,
        }]
        self.assertTrue(self.valid(result))

    def test_need_evidence_without_unresolved_question_is_rejected(self):
        result = base_result()
        result["decision"] = "need_evidence"
        result["issues"] = [{
            "issue_id": "I-1",
            "dimension_id": "DIM-1",
            "category": "evidence_gap",
            "blocking": True,
            "detail": "缺少来源",
            "evidence_ids": [],
            "evidence_ref_ids": [],
            "counterexample_ref_ids": [],
            "unresolved_question_ids": [],
            "required_action": "补证",
        }]
        self.assertFalse(self.valid(result))

    def test_unable_to_review_requires_execution_blocker(self):
        result = base_result()
        result["decision"] = "unable_to_review"
        result["issues"] = [{
            "issue_id": "I-1",
            "dimension_id": "DIM-1",
            "category": "execution_blocker",
            "blocking": True,
            "detail": "原始文件无法读取",
            "evidence_ids": [],
            "evidence_ref_ids": [],
            "counterexample_ref_ids": [],
            "unresolved_question_ids": [],
            "required_action": "恢复原始文件后重新审查",
        }]
        result["evidence_references"] = []
        result["claim_assessments"] = []
        result["dimension_assessments"] = [{
            "dimension_id": "DIM-1",
            "assessment": "not_assessed",
            "evidence_ref_ids": [],
            "counterexample_check": counterexample("not_assessed"),
            "support_scope": "无法读取输入，未作实质判断",
            "unresolved_question_ids": [],
        }]
        self.assertTrue(self.valid(result))

    def test_reject_requires_blocking_academic_defect(self):
        result = base_result()
        result["decision"] = "reject"
        result["issues"] = [{
            "issue_id": "I-1",
            "dimension_id": "DIM-1",
            "category": "academic_defect",
            "blocking": True,
            "detail": "核心命题与已核实材料相矛盾",
            "evidence_ids": ["MAT-01"],
            "evidence_ref_ids": ["ER-1"],
            "counterexample_ref_ids": ["ER-1"],
            "unresolved_question_ids": [],
            "required_action": "重新界定研究问题",
        }]
        result["claim_assessments"][0].update(
            assessment="contradicted",
            counterexample_check=counterexample("found", ["ER-1"]),
        )
        result["dimension_assessments"][0].update(
            assessment="unresolved",
            counterexample_check=counterexample("found", ["ER-1"]),
        )
        result["evidence_references"][0]["relation"] = "counterexample"
        self.assertTrue(self.valid(result))

    def test_issue_must_link_evidence_and_unresolved_reference_arrays(self):
        result = base_result()
        result["issues"] = [{
            "issue_id": "I-1",
            "dimension_id": "DIM-1",
            "category": "suggestion",
            "blocking": False,
            "detail": "建议明确案例边界",
            "evidence_ids": [],
            "required_action": "补充边界说明",
        }]
        self.assertFalse(self.valid(result))

    def test_early_review_can_explicitly_have_no_empirical_claims(self):
        result = base_result()
        result["evidence_references"] = []
        result["claim_assessments"] = []
        result["dimension_assessments"] = [{
            "dimension_id": "DIM-1",
            "assessment": "not_applicable",
            "evidence_ref_ids": [],
            "counterexample_check": counterexample("not_applicable"),
            "support_scope": "初始学术价值审查尚无经验主张，按 D09 claims_scope 明确不适用",
            "unresolved_question_ids": [],
        }]
        self.assertTrue(self.valid(result))

    def test_unknown_fields_remain_rejected(self):
        result = base_result()
        result["formal_pass"] = True
        self.assertFalse(self.valid(result))


if __name__ == "__main__":
    unittest.main()
