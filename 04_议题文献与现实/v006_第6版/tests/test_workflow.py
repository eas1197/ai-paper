"""Synthetic fixtures only: test code gates, never certify a real research corpus."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import runtime as rt
import providers
import stage04 as s4

s5 = rt.load_stage("05")
STAMP = "2026-11-15T10:00:00+08:00"


class TestPdfReader:
    """Only for explicitly synthetic unit tests, no production parser bypass."""
    def inspect(self, path):
        data = Path(path).read_bytes()
        if not data.startswith(b"%PDF-"):
            raise ValueError("not PDF")
        return data.decode("utf-8").split("\n", 1)[1].split("\f")


def direct(identity, document, digest, quote, paper=None, page=None):
    return {"evidence_id": identity, "document_id": document, "paper_id": paper,
            "source_sha256": digest, "locator": "PDF p1" if page else "原文第1段", "pdf_page": page,
            "short_excerpt": quote, "paraphrase": "TEST对应短摘的释义", "evidence_class": "direct",
            "stance": "support", "basis_evidence_ids": [], "extraction_method": "TEST_fixture",
            "review_status": "verified", "reviewer": "TEST_reader", "verified_at": STAMP}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(rt, "run_directory", lambda run_id: self.root / "runs" / run_id)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def inputs(self, mid, **kwargs):
        return dict({"run_id": "TEST_only", "base_dir": str(self.root)}, **kwargs)

    def config(self):
        return {"as_of": "2026-11-15"}

    def fixture04(self):
        papers, reviews, evidence, core, dialogue, docs = [], {}, [], [], [], []
        for i in range(100):
            pid = f"P_TEST_{i:03d}"
            abstract = f"TEST摘要{i}：本研究考察资源与结果的关联。"
            papers.append({"paper_id": pid, "title": f"TEST论文{i}", "authors": [f"TEST作者{i}"], "year": 2024,
                           "journal": "中国社会科学", "doi": f"10.0000/test{i}", "abstract": abstract})
            reviews[pid] = {"abstract": {"status": "abstract_read", "inclusion_status": "included",
                          "abstract_sha256": rt.value_hash(abstract) if False else __import__('hashlib').sha256(abstract.encode()).hexdigest(),
                          "reader": "TEST_reader", "read_at": STAMP, "notes": "TEST摘要阅读记录",
                          "relevance": "TEST议题相关", "authority_basis": "TEST来源核查", "no_relation_reason": "TEST测试仅前一篇抽取关系"}}
            if i < 25:
                content = f"TEST论文{i}。TEST原命题{i}：资源与结果相关。\fTEST论文{i}的设计、结果和局限。"
                pdf = self.root / f"full{i}.pdf"
                pdf.write_bytes(b"%PDF-TEST\n" + content.encode())
                did = "DOC_FULL_" + rt.value_hash(pid)[:20]
                reviews[pid]["fulltext"] = {"path": str(pdf), "status": "fulltext_read", "sha256": rt.sha(pdf),
                           "identity_verified": True, "identity_basis": "TEST核对题名作者", "complete": True,
                           "reader": "TEST_reader", "read_at": STAMP, "notes": "TEST全文阅读记录", "page_spans": [[1, 2]]}
                eid = f"E_FULL_{i}"
                evidence.append(direct(eid, did, rt.sha(pdf), f"TEST原命题{i}：资源与结果相关。", pid, 1))
                core.append({"paper_id": pid, **{k: "TEST说明" for k in ("selection_reason", "relevance", "theory_authority", "design_quality", "journal_authority", "recency", "perspective_balance")}})
                dialogue.append({"paper_id": pid, "evidence_ids": [eid], **{k: "TEST已核查" for k in ("original_question", "original_relation", "theory", "design", "main_finding", "scope", "limitations", "page_locator", "our_agreement", "our_difference", "our_test", "planned_citation_location")}})
        for kind in ("policy", "news"):
            p = self.root / (kind + ".txt")
            p.write_text(f"TEST{kind}原文：促进公平。", encoding="utf-8")
            docs.append({"document_id": "DOC_" + kind, "path": str(p), "source_id": "S_TEST_" + kind,
                         "retrieved_at": STAMP, "access_basis": "TEST自建", "kind": kind, "url": "https://example.invalid/" + kind})
            evidence.append(direct("E_" + kind, "DOC_" + kind, rt.sha(p), f"TEST{kind}原文：促进公平。"))
        pid = papers[0]["paper_id"]
        evidence.append(direct("E_ABS", "DOC_ABS_" + rt.value_hash(pid)[:20], reviews[pid]["abstract"]["abstract_sha256"], "本研究考察资源与结果的关联。", pid))
        contexts = [{"context_id": "CTX_" + kind, "type": kind, "title": "TEST原文", "primary_url": "https://example.invalid/" + kind,
                     "publisher": "TEST主体", "published_at": "2025-01-01", "retrieved_at": STAMP, "event_date": "2025-01-01",
                     "geography": "TEST地区", "population": "TEST对象", "claim": "TEST制度目标", "relevance": "TEST议题相关",
                     "reviewer": "TEST_reader", "verified_at": STAMP, "verification_status": "verified", "evidence_ids": ["E_" + kind],
                     "national_level": True, "current_validity": "verified_current", "institutional_goal": "TEST目标", "validity_basis": "TEST现行性核查"} for kind in ("policy", "news")]
        annotation = {"topic_scope": {"issue_candidates": [{"topic_id": "TOPIC_TEST", "issue": "TEST通用议题", "evidence_ids": ["E_policy", "E_FULL_0"],
                         **{k: "TEST比较依据" for k in ("reality_value", "theory_value", "existing_explanations", "researchability", "data_conditions")}}], "selected_topic_id": "TOPIC_TEST"},
                     "paper_reviews": reviews, "documents": docs, "evidence": evidence, "core_selection": core, "dialogue": dialogue, "contexts": contexts,
                     "relations": [{"relation_id": "R_TEST", "paper_id": pid, "X": "TEST资源", "Y": "TEST结果", "relation_type": "association", "direction": "positive",
                        "unit": "TEST个体", "scope": {k: "unknown" for k in ("population", "geography", "period", "institution", "measurement", "data", "design")}, "claimed_strength": "association", "supported_strength": "association",
                        "evidence_ids": ["E_ABS"], "read_basis": "abstract", "uncertainty": "TEST不识别因果", "review_status": "verified"}],
                     "views": [{"view_id": f"VIEW_{i}", "name": f"TEST路径{i}", "central_proposition": "TEST命题", "logical_chain": "X→Y", "concept_roles": {"X": "TEST资源", "Y": "TEST结果"},
                         "relation_ids": ["R_TEST"], "core_paper_ids": [f"P_TEST_{i:03d}"], "scope": "TEST范围", "unexplained_part": "TEST未解释部分",
                         "fulltext_review_status": "verified", "evidence_ids": [f"E_FULL_{i}"]} for i in (0, 1)],
                     "view_links": [{"link_id": "LINK_TEST", "from_view": "VIEW_0", "to_view": "VIEW_1", "relation_type": "complementary", "relationship_explanation": "TEST互补说明", "evidence_ids": ["E_FULL_0", "E_FULL_1"], "review_status": "verified"}],
                     "selection_balance": {k: {"assessment": "TEST选择权衡", "search_scope": "TEST检索范围", "paper_ids": ["P_TEST_000"]} for k in ("classic", "recent", "counterevidence")},
                     "journal_aliases": [{"original": original, "decision": "not_used", "reason": "TEST本次未使用该刊"} for original in ("经济学研究", "探索与证明")],
                     "searches": [{"search_id": "SEARCH_TEST", "provider": "TEST本地", "query": "TEST关键词", "searched_at": STAMP, "inclusion_rule": "TEST相关", "exclusion_rule": "TEST无关", "access_status": "authorized_export", "coverage_limit": "TEST有限样本"}]}
        source = self.root / "papers.json"
        rt.write(source, papers)
        path = self.root / "annotations04.json"
        rt.write(path, annotation)
        inputs = self.inputs("04", theme="TEST主题", annotations=str(path), literature=[{"source_id": "S_TEST", "path": str(source), "format": "json", "retrieved_at": STAMP, "access_basis": "TEST自建资料"}])
        return inputs, annotation, path

    def passed04(self):
        inputs, _, _ = self.fixture04()
        first = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        gate = rt.load(Path(first["attempt_path"]) / "gate_report.json")
        self.assertEqual(len(gate["errors"]), 1, gate["errors"])
        review = self.root / "review04.json"
        rt.write(review, dict(content_sha256=gate["content_sha256"], decision="accepted", reviewer="TEST_reviewer", reviewed_at=STAMP, assessment="TEST仅验证程序放行分支"))
        inputs["quality_review"] = str(review)
        second = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        self.assertEqual(second["status"], "passed", rt.load(Path(second["attempt_path"]) / "gate_report.json")["errors"])
        return second

    def fixture05(self, upstream):
        path = self.root / "questionnaire.txt"
        path.write_text("TEST问卷：Q1您的资源情况？ Q2您的结果情况？", encoding="utf-8")
        me = [direct("E_Q1", "DOC_QUESTION", rt.sha(path), "Q1您的资源情况？"), direct("E_Q2", "DOC_QUESTION", rt.sha(path), "Q2您的结果情况？")]
        variables = [{"variable_id": "V_" + role, "dataset": "TEST_CF", "wave": "2024", "source_variable": "Q" + str(i), "concept": "TEST" + role,
                      "role": role, "question_id": "Q" + str(i), "question_text": q, "questionnaire_locator": "TEST p1", "value_labels": {"1": "TEST类别"}, "special_missing": {},
                      "population": "TEST对象", "measurement_time": "TEST时点", "construction": "TEST原值", "rationale": "TEST理论依据", "missing_policy": "TEST预定缺失",
                      "evidence_ids": ["E_Q" + str(i)], "review_status": "verified", "feasibility": "feasible"} for i, role, q in [(1, "X", "Q1您的资源情况？"), (2, "Y", "Q2您的结果情况？")]]
        candidate = {"candidate_id": "CAND_TEST", "question": "TEST资源与结果如何关联？", "trigger": "T", "primary_advance": "same_level_gap", "secondary_advances": [],
                     "baseline_paper_ids": ["P_TEST_000"], "evidence_ids": ["E_FULL_0"], "context_ids": ["CTX_policy"],
                     "novelty_search": {"scope": "TEST范围", "queries": ["TEST查询"], "coverage_limit": "TEST范围有限", "reviewed_fulltext_ids": ["P_TEST_000"], "conclusion": "TEST范围内限定问题"},
                     "status": "accepted", **{k: "TEST问题依据" for k in ("original_proposition", "original_scope", "retained_part", "proposed_change", "importance", "counterevidence", "dataset_feasibility")}}
        h = {"hypothesis_id": "H_TEST", "candidate_id": "CAND_TEST", "kind": "H", "research_question": candidate["question"], "baseline_paper_ids": ["P_TEST_000"], "evidence_ids": ["E_FULL_0"],
             "X": "TEST资源", "Y": "TEST结果", "mechanism": "TEST理论机制", "scope": "TEST范围", "expected_pattern": "TEST正向关联", "falsification": "TEST负向或区间与预期不符", "competing_explanations": ["TEST竞争解释"],
             "dataset_feasibility": "TEST元数据支持", "causal_claim_level": "association", "variable_ids": ["V_X", "V_Y"], "confirmatory": True, "exploratory": False, "review_status": "accepted"}
        dialogue = {"candidate_id": "CAND_TEST", "hypothesis_id": "H_TEST", "baseline_paper_id": "P_TEST_000", "evidence_ids": ["E_FULL_0"], "status": "verified",
                    **{k: "TEST全文对话" for k in ("original_proposition", "original_scope", "fulltext_locator", "retained_part", "proposed_change", "advance_type", "mechanism_reason", "expected_pattern", "falsification")}}
        design = {"question": candidate["question"], "hypothesis_ids": ["H_TEST"], "unit": "TEST个体", "estimand": "TEST关联", "primary_outcomes": ["V_Y"], "primary_models": ["TEST线性回归"],
                  "dag": "TEST X→Y，时序待观测设计限定", "control_rationale": [], "sample_rules": ["TEST预先纳入规则"], "exclusions_policy": "TEST不依结果删样本", "missing_policy": "TEST方案",
                  "survey_design": {k: {"status": "not_applicable", "rationale": "TEST夹具不包含抽样"} for k in ("weights", "strata", "psu")},
                  **{k: "TEST预定方案" for k in ("timing", "inference", "diagnostics", "robustness", "multiple_testing_policy", "power_and_precision")}, "seed": 42}
        annotation = {"candidates": [candidate], "route_assessments": [{"gap_type": k, "decision": "candidate" if k == "same_level_gap" else "not_supported", "reason": "TEST路线审查", "evidence_ids": ["E_FULL_0"]} for k in rt.GAP_TYPES],
                      "same_level_reviews": [{"candidate_id": "CAND_TEST", "checks": {k: {"passed": True, "reason": "TEST可比依据"} for k in rt.CHECKS}, "overlap_evidence_ids": ["E_FULL_0"], "decision": "comparable"}],
                      "literature_dialogue": [dialogue], "hypotheses": [h], "metadata_documents": [{"document_id": "DOC_QUESTION", "source_id": "S_Q", "path": str(path), "kind": "questionnaire", "retrieved_at": STAMP, "access_basis": "TEST自建问卷"}],
                      "measurement_evidence": me, "measurements": variables, "analysis_design": design, "analysis_phase": "pre_analysis", "freeze_requested": True,
                      "writing_handoff": {k: {"instruction": "TEST写作输入", "candidate_ids": ["CAND_TEST"], "evidence_ids": ["E_FULL_0"]} for k in ("introduction", "literature_end", "theory_derivation", "conclusion_return")}}
        concept = {"name": "TEST资源", "kind": "resource_dimension", "abstraction": "TEST层级", "unit": "TEST个体", "role": "X", "dimension": "TEST资源维度", "timing": "TEST事前"}
        annotation["concept_audits"] = [{"candidate_id": "CAND_TEST", "baseline": [concept], "proposed": dict(concept, name="TEST时间资源"),
            "overlap_search": "TEST全文覆盖核查", "conclusion": "TEST限定范围内可比", "reviewer": "TEST_reader", "reviewed_at": STAMP, "review_status": "verified"}]
        annotation["reality_theory_links"] = [{"candidate_id": "CAND_TEST", "reality_statement": "TEST现实情境", "policy_relevance": "TEST政策直接相关", "theory_statement": "TEST原理论范围",
            "question_connection": "TEST具体关系待解释", "context_ids": ["CTX_policy", "CTX_news"], "evidence_ids": ["E_policy", "E_news", "E_FULL_0"], "unexplained_relationship": "TEST理论尚未覆盖的关系"}]
        annotation["writing_handoff"]["introduction"]["policy_evidence_ids"] = ["E_policy"]
        path = self.root / "annotations05.json"
        rt.write(path, annotation)
        return self.inputs("05", upstream=str(Path(upstream["attempt_path"]) / "stage_manifest.json"), annotations=str(path)), annotation, path

    def test_empty_joint_flow_is_needs_review_not_false_success(self):
        first = s4.execute(s4.plan(self.inputs("04"), self.config()))
        second = s5.execute(s5.plan(self.inputs("05", upstream=str(Path(first["attempt_path"]) / "stage_manifest.json")), self.config()))
        self.assertEqual((first["status"], second["status"]), ("needs_review", "needs_review"))
        self.assertFalse(rt.load(Path(second["attempt_path"]) / "analysis_design.json")["frozen"])
        with self.assertRaises(ValueError):
            s4.export(first["attempt_path"])

    def test_100_25_gate_requires_reviewer_and_can_pass_with_bound_review(self):
        result = self.passed04()
        self.assertEqual(rt.integrity(result["attempt_path"]), [])
        output = s4.export(result["attempt_path"])
        self.assertTrue(Path(output["path"]).is_file())
        gate = rt.load(Path(result["attempt_path"]) / "gate_report.json")
        self.assertEqual(gate["counts"]["abstracts_read"], 100)
        self.assertEqual(gate["counts"]["core_read"], 25)
        with closing(sqlite3.connect(Path(result["attempt_path"]) / "knowledge.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM papers").fetchone()[0], 100)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_full_joint_g5_freeze_and_tamper_detection(self):
        up = self.passed04()
        inputs, _, _ = self.fixture05(up)
        first = s5.execute(s5.plan(inputs, self.config()))
        report = rt.load(Path(first["attempt_path"]) / "gate_report.json")
        self.assertEqual(len(report["errors"]), 1, report["errors"])
        review = self.root / "review05.json"
        rt.write(review, dict(content_sha256=report["content_sha256"], decision="accepted", reviewer="TEST_reviewer", reviewed_at=STAMP, assessment="TEST仅验证程序分支"))
        inputs["quality_review"] = str(review)
        second = s5.execute(s5.plan(inputs, self.config()))
        self.assertEqual(second["status"], "passed", rt.load(Path(second["attempt_path"]) / "gate_report.json")["errors"])
        frozen = rt.load(Path(second["attempt_path"]) / "analysis_design.json")
        self.assertTrue(frozen["frozen"])
        with closing(sqlite3.connect(Path(second["attempt_path"]) / "knowledge.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM hypotheses").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(rt.integrity(second["attempt_path"]), [])
        s5.export(second["attempt_path"])
        (Path(up["attempt_path"]) / "bundle.json").write_text("{}", encoding="utf-8")
        self.assertTrue(rt.integrity(second["attempt_path"]))
        with self.assertRaises(ValueError):
            s5.export(second["attempt_path"])

    def test_unapproved_source_loses_abstract_and_core_credit(self):
        result = self.passed04()
        work = Path(result["attempt_path"])
        bundle = rt.load(work / "bundle.json")
        chosen = bundle["core"][0]["paper_id"]
        next(p for p in bundle["papers"] if p["paper_id"] == chosen)["journal"] = "Other International Journal"
        report = s4.validate(bundle, {"work": work})
        self.assertEqual(report["counts"]["abstracts_read"], 99)
        self.assertEqual(report["counts"]["core_read"], 24)
        self.assertTrue(any("不在指定文献库" in error for error in report["errors"]))

    def test_changed_plan_and_decreased_targets_are_rejected(self):
        inputs, _, path = self.fixture04()
        plan = s4.plan(inputs, self.config())
        rt.write(path, {})
        with self.assertRaises(ValueError):
            s4.execute(plan)
        with self.assertRaises(ValueError):
            s4.plan(self.inputs("04"), {"abstract_target": 15})
        with self.assertRaises(ValueError):
            rt.inside(self.root, "../escape")
        with self.assertRaises(ValueError):
            s4.plan(self.inputs("04", run_id="../escape"))

    def test_bad_excerpt_wrong_pages_and_unread_fulltext_do_not_count(self):
        inputs, annotation, path = self.fixture04()
        annotation["evidence"][0]["short_excerpt"] = "TEST这句话从未出现"
        annotation["evidence"][1]["pdf_page"] = 99
        annotation["paper_reviews"]["P_TEST_002"]["fulltext"]["status"] = "not_read"
        annotation["paper_reviews"]["P_TEST_003"]["fulltext"]["page_spans"] = [[1, 1]]
        rt.write(path, annotation)
        result = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        report = rt.load(Path(result["attempt_path"]) / "gate_report.json")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(report["counts"]["core_read"], 23)
        self.assertTrue(any("短摘" in e for e in report["errors"]))
        self.assertTrue(any("pdf_page" in e for e in report["errors"]))

    def test_g5_rejects_keyword_gap_bridge_missing_and_post_analysis(self):
        up = self.passed04()
        inputs, annotation, path = self.fixture05(up)
        annotation["candidates"][0]["novelty_search"]["basis"] = "abstract_keyword_absence"
        annotation["same_level_reviews"][0]["checks"]["dimension"]["passed"] = False
        annotation["analysis_phase"] = "post_analysis"
        annotation["analysis_design"]["frozen"] = True
        annotation["measurements"][0]["question_text"] = "TEST模型补造的题目"
        rt.write(path, annotation)
        result = s5.execute(s5.plan(inputs, self.config()))
        errors = rt.load(Path(result["attempt_path"]) / "gate_report.json")["errors"]
        for phrase in ("摘要缺词", "桥接", "倒填", "自报", "问卷原文"):
            self.assertTrue(any(phrase in e for e in errors), (phrase, errors))

    def test_retry_is_new_attempt_old_attempt_is_not_overwritten(self):
        p = s4.plan(self.inputs("04"), self.config())
        a = s4.execute(p)
        old = (Path(a["attempt_path"]) / "stage_manifest.json").read_bytes()
        b = s4.execute(p)
        self.assertNotEqual(a["attempt_path"], b["attempt_path"])
        self.assertEqual(old, (Path(a["attempt_path"]) / "stage_manifest.json").read_bytes())

    def test_model_output_stays_unverified_and_has_call_budget(self):
        class Model:
            provider_id, model_version = "TEST", "TEST1"
            def propose(self, task):
                return {"claim": "TEST不能自动当作已验证事实"}
        result = s4.execute(s4.plan(self.inputs("04"), self.config()), {"model_provider": Model()})
        proposals = rt.load(Path(result["attempt_path"]) / "model_proposals.json")
        self.assertTrue(all(p["review_status"] == "unverified" for p in proposals))
        self.assertEqual(result["status"], "needs_review")
        with self.assertRaises(ValueError):
            s4.execute(s4.plan(self.inputs("04"), {"model_call_limit": 1}), {"model_provider": Model()})
        run = rt.load(self.root / "runs/TEST_only/run_manifest.json")
        self.assertEqual(run["stages"][0]["status"], "failed")
        self.assertFalse((self.root / "runs/TEST_only/.research.lock").exists())

    def test_non_pdf_is_not_archived_as_core_fulltext(self):
        inputs, annotation, path = self.fixture04()
        html = self.root / "login.pdf"
        html.write_text("<html>login</html>", encoding="utf-8")
        annotation["paper_reviews"]["P_TEST_000"]["fulltext"]["path"] = str(html)
        rt.write(path, annotation)
        result = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        self.assertTrue(rt.load(Path(result["attempt_path"]) / "bundle.json")["archive_errors"])

    def test_reexecute04_marks05_stale_and_prohibits_old_handoff(self):
        up = self.passed04()
        inputs, _, _ = self.fixture05(up)
        five = s5.execute(s5.plan(inputs, self.config()))
        s4.execute(s4.plan(self.inputs("04"), self.config()))
        run = rt.load(self.root / "runs/TEST_only/run_manifest.json")
        self.assertEqual(next(s for s in run["stages"] if s["stage_id"] == "05")["status"], "stale")
        with self.assertRaises(ValueError):
            s4.export(up["attempt_path"])

    def test_cyclic_inference_and_old_news_are_rejected(self):
        inputs, annotation, path = self.fixture04()
        a = dict(annotation["evidence"][0], evidence_id="E_CYCLE_A", evidence_class="inference", basis_evidence_ids=["E_CYCLE_B"])
        b = dict(a, evidence_id="E_CYCLE_B", basis_evidence_ids=["E_CYCLE_A"])
        annotation["evidence"] += [a, b]
        annotation["contexts"][1]["published_at"] = "2020-01-01"
        rt.write(path, annotation)
        result = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        errors = rt.load(Path(result["attempt_path"]) / "gate_report.json")["errors"]
        self.assertTrue(any("循环" in e for e in errors))
        self.assertTrue(any("近三年" in e for e in errors))

    def test_same_pdf_cannot_satisfy_multiple_core_papers(self):
        inputs, annotation, path = self.fixture04()
        first = annotation["paper_reviews"]["P_TEST_000"]["fulltext"]
        second = annotation["paper_reviews"]["P_TEST_001"]["fulltext"]
        second.update(path=first["path"], sha256=first["sha256"])
        rt.write(path, annotation)
        result = s4.execute(s4.plan(inputs, self.config()), {"pdf_reader": TestPdfReader()})
        errors = rt.load(Path(result["attempt_path"]) / "gate_report.json")["errors"]
        self.assertTrue(any("同一PDF" in e for e in errors))

    def test_joint_plan_checks_future05_annotations_before04_execution(self):
        import research
        input05 = self.root / "future05.json"
        rt.write(input05, {})
        future = rt.make_plan("05", self.inputs("05", annotations=str(input05)))
        joint = {"kind": "04_then_05", "stage04_plan": s4.plan(self.inputs("04")), "stage05_inputs": future["inputs"], "stage05_input_files": future["input_files"], "config": {}}
        rt.write(input05, {"changed": True})
        with self.assertRaises(ValueError):
            research.execute_plan(joint)
        self.assertFalse((self.root / "runs/TEST_only").exists())

    def test_active_run_lock_is_not_stolen(self):
        run = self.root / "runs/TEST_only"
        run.mkdir(parents=True)
        (run / ".research.lock").write_text("TEST活跃进程", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            s4.execute(s4.plan(self.inputs("04")))
        self.assertTrue((run / ".research.lock").exists())

    def test_recording_failure_still_releases_run_lock(self):
        with patch.object(rt, "update_run", side_effect=OSError("TEST状态记录失败")):
            with self.assertRaises(OSError):
                s4.execute(s4.plan(self.inputs("04")))
        self.assertFalse((self.root / "runs/TEST_only/.research.lock").exists())


class ProviderTests(unittest.TestCase):
    def row(self, **kwargs):
        return dict(title="TEST标题", authors=["TEST作者"], year="2024", doi=None, source_id="S_TEST", source_record_id=None,
                    abstract="TEST摘要", original_paper_id=None, fulltext_source_path=None, **kwargs)

    def test_doi_source_and_transitive_dedup_and_stable_ids(self):
        a = self.row()
        a["source_record_id"] = "K1"
        b = dict(a, doi="10.0000/test")
        c = dict(b, source_id="S_OTHER", source_record_id="K2")
        catalog = {}
        first, _ = providers.deduplicate([a], catalog)
        second, conflict = providers.deduplicate([a, b, c], catalog)
        self.assertEqual(len(second), 1)
        self.assertFalse(conflict)
        self.assertEqual(first[0]["paper_id"], second[0]["paper_id"])

    def test_conflicting_doi_is_not_silently_accepted(self):
        a = self.row()
        a["doi"] = "10.0000/a"
        b = dict(a, doi="10.0000/b")
        papers, conflicts = providers.deduplicate([a, b])
        self.assertEqual(papers[0]["identity_status"], "conflict")
        self.assertEqual(len(conflicts), 1)

    def test_ris_multiline_and_malformed_trailing_record(self):
        raw = "TY  - JOUR\nTI  - TEST标题\nAU  - TEST作者\nPY  - 2024\nAB  - TEST摘要\n  TEST续行\nER  -\n"
        result = providers.LocalLiteratureProvider.ris(raw)
        self.assertIn("TEST续行", result[0]["abstract"])
        with self.assertRaises(ValueError):
            providers.LocalLiteratureProvider.ris(raw.replace("ER  -", ""))

    def test_same_title_different_authors_not_merged(self):
        a = self.row()
        b = dict(a, authors=["TEST不同作者"])
        self.assertEqual(len(providers.deduplicate([a, b])[0]), 2)

    def test_zotero_readonly_import_leaves_original_database_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "zotero.sqlite"
            with closing(sqlite3.connect(file)) as db:
                db.executescript("CREATE TABLE itemData(itemID,fieldID,valueID); CREATE TABLE fields(fieldID,fieldName); CREATE TABLE itemDataValues(valueID,value); CREATE TABLE items(itemID,key,itemTypeID); CREATE TABLE itemTypes(itemTypeID,typeName); CREATE TABLE deletedItems(itemID); CREATE TABLE itemCreators(itemID,creatorID,creatorTypeID,orderIndex); CREATE TABLE creators(creatorID,lastName,firstName); CREATE TABLE itemAttachments(itemID,parentItemID,path); INSERT INTO itemTypes VALUES(1,'journalArticle'); INSERT INTO items VALUES(1,'TEST_KEY',1); INSERT INTO fields VALUES(1,'title'); INSERT INTO itemDataValues VALUES(1,'TEST只读题名'); INSERT INTO itemData VALUES(1,1,1);")
                db.executescript("CREATE TABLE creatorTypes(creatorTypeID,creatorType); INSERT INTO creatorTypes VALUES(8,'author'); INSERT INTO creators VALUES(1,'TEST作者',''); INSERT INTO itemCreators VALUES(1,1,8,0);")
            before = rt.sha(file)
            rows = providers.LocalLiteratureProvider().read({"path": str(file), "format": "zotero", "source_id": "S_TEST", "access_basis": "TEST自建", "retrieved_at": STAMP})
            self.assertEqual(rows[0]["title"], "TEST只读题名")
            self.assertEqual(rows[0]["authors"], ["TEST作者"])
            self.assertEqual(rt.sha(file), before)

    def test_csv_multiline_abstract_and_authors_are_preserved(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "papers.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["title", "authors", "abstract"])
                writer.writeheader()
                writer.writerow({"title": "TEST题名", "authors": '["甲", "乙"]', "abstract": "TEST第一行\nTEST第二行"})
            row = providers.LocalLiteratureProvider().read({"path": str(path), "source_id": "S_TEST", "access_basis": "TEST自建", "retrieved_at": STAMP})[0]
            self.assertEqual(row["authors"], ["甲", "乙"])
            self.assertIn("\n", row["abstract"])

    def test_production_pdf_reader_rejects_login_and_corrupt_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bad.pdf"
            file.write_bytes(b"<html>TEST login</html>")
            with self.assertRaises(ValueError):
                providers.PdfReader().inspect(file)
            file.write_bytes(b"%PDF-1.4\nTEST broken PDF without objects")
            with self.assertRaises(ValueError):
                providers.PdfReader().inspect(file)


if __name__ == "__main__":
    unittest.main(verbosity=2)
