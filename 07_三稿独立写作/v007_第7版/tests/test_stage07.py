"""技术夹具只验证工作流，不计入课题验收。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "tools"))
import stage07
from manuscript07 import parse_structure, read_checklist, reported_value
from language07 import style_findings
from runtime import ROOT, file_lock, load, run_directory, sha, write


class WritingTest(unittest.TestCase):
    def test_rejected_paragraph(self):
        bad = "## 五、实证结果\n中频组两项估计的区间均跨零。这个结果表明，样本能够辨认高频组与低频组的正向联系，却不足以确立“每升一级就增加多少”的剂量关系。不能把等级当成相同长度的使用时数。"
        self.assertEqual({x["rule_id"] for x in style_findings(bad)}, {"L01", "L02", "L03", "L04"})
        good = "## 五、实证结果\n和低频组相比，高频组的朋友聚会率高9.10个百分点，亲属聚会率高5.58个百分点。中频组的两项差异估计尚不精确。"
        self.assertEqual(style_findings(good), [])

    def test_previous_run_and_short_essay_are_blocked(self):
        run = run_directory("ambiguity_20261118")
        if not (run / "暧昧期.md").is_file():
            self.skipTest("此副本没有上一轮实际产物")
        plan = stage07.plan({"run_id": run.name})
        self.assertEqual(plan["status"], "needs_review")
        self.assertIsNone(plan["pack_id"])
        for gate in ("G2", "G3", "G4", "G5", "G6"):
            self.assertTrue(any(gate in e for e in plan["errors"]))
        architecture = load(MODULE / "manifest.json")["writing_architecture"]
        profile = load(ROOT / architecture["profile_path"])
        errors = []
        parse_structure((run / "暧昧期.md").read_text(encoding="utf-8-sig"), None, profile, errors)
        self.assertTrue(any("六项正文任务" in e for e in errors))
        self.assertTrue(any("关键词" in e for e in errors))

    def test_numeric_claim_rejects_wrong_value_and_wrong_sign(self):
        row = {"estimate": 0.12751}
        self.assertTrue(reported_value({"display": "0.128", "field": "estimate"}, row, "系数为0.128。"))
        self.assertFalse(reported_value({"display": "0.128", "field": "estimate"}, row, "系数为−0.128。"))
        self.assertFalse(reported_value({"display": "0.100", "field": "estimate"}, row, "系数为0.100。"))

    def test_prepare_review_export_and_stale_detection(self):
        with tempfile.TemporaryDirectory(dir=MODULE / "tests") as folder:
            run = Path(folder).resolve()
            request_path = self.fixture(run)
            with patch.object(stage07, "run_directory", return_value=run):
                p = stage07.plan({"run_id": run.name, "input": str(request_path)})
                self.assertEqual(p["status"], "ready", p["errors"])
                stage07.prepare(p)
                request = load(request_path)
                draft = request["drafts"]["A"]
                draft["pack_id"] = p["pack_id"]
                write(request_path, request)
                result = stage07.execute(p)
                self.assertEqual(result["status"], "needs_review", result)
                attempt = Path(result["attempt_path"])
                review = load(attempt / "drafts/A/quality_review_request.json")
                self.assertEqual(review["technical_errors"], [])
                with self.assertRaises(ValueError):
                    stage07.export(attempt)
                write(run / "review.json", dict(review, decision="accepted", reviewer="技术测试夹具",
                                               reviewed_at="2026-11-18", assessment="验证复核记录与内容哈希的绑定"))
                draft["review"] = "review.json"
                write(request_path, request)
                result = stage07.execute(p)
                self.assertEqual(result["status"], "passed", result)
                attempt = Path(result["attempt_path"])
                exported = stage07.export(attempt)
                self.assertEqual(exported["destination"], "single_delivery")
                self.assertFalse(exported["submission_enabled"])
                self.assertEqual([p.name for p in (attempt / "drafts").iterdir()], ["A"])
                (attempt / "drafts/A/manuscript.md").write_text("产物改变", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "完整性检查失败"):
                    stage07.export(attempt)

    def fixture(self, run):
        architecture = load(MODULE / "manifest.json")["writing_architecture"]
        style = load(ROOT / "00_项目控制/v003_第3版/project_config.json")["writing"]["language_style"]
        resources = []
        for mid, files in (("02", [architecture["profile_path"], architecture["guide_path"]]),
                           ("03", [style["profile_path"]])):
            path = run / f"resource_{mid}.json"
            report = run / f"gate_{mid}.json"
            write(report, {"status": "passed"})
            write(path, {"module_id": mid, "status": "passed", "business_gate_report": str(report),
                         "files": [file_lock(ROOT / file) for file in [*files, report]]})
            resources.append({"module_id": mid, "snapshot_manifest_path": str(path),
                              "manifest_sha256": sha(path), "status": "passed"})
        paper = "fixture-paper"
        evidence = "fixture-evidence"
        result = "fixture-result"
        core = [{"paper_id": f"fixture-{i}"} for i in range(25)]
        stage04 = {"core": core, "dialogue": core, "papers": [{"paper_id": paper}], "documents": [],
                   "evidence": [{"evidence_id": evidence, "paper_id": paper}]}
        method_binding = {"resource_id": "fixture", "status": "passed"}
        rows = []
        for mid in ("04", "05", "06"):
            work = run / f"stage_{mid}/attempt_001"
            report = work / "gate_report.json"
            gate = {"gate": f"G{int(mid)}", "status": "passed"}
            if mid == "04":
                gate.update(source_eligible_paper_ids=[paper, *[row["paper_id"] for row in core]], counts={"abstracts_read": 100})
            if mid == "06":
                gate["phase"] = "approve"
            write(report, gate)
            if mid == "05":
                write(work / "analysis_design.json", {"frozen": True, "pre_analysis": True, "design_sha256": "fixture"})
                stage05 = {"upstream": {"manifest_sha256": rows[-1]["manifest_sha256"]},
                           "metadata_documents": [], "measurement_evidence": []}
            if mid == "06":
                stage06 = {k: ["fixture"] for k in ("actual_run_at", "sample_flow", "models", "method_references", "reproduction")}
                stage06.update(upstream={"path": rows[-1]["manifest_path"], "design_sha256": "fixture"},
                               protocol={"seed": 1}, results=[{"result_id": result, "estimate": 0.125}],
                               method_library_binding=method_binding)
            bundle = {"04": lambda: stage04, "05": lambda: stage05, "06": lambda: stage06}[mid]()
            write(work / "bundle.json", dict(bundle, run_id=run.name))
            path = work / "stage_manifest.json"
            write(path, {"run_id": run.name, "stage_id": mid, "attempt": 1, "status": "passed",
                         "gate_report": report.name, "input_files": [],
                         "output_files": [file_lock(p) for p in work.iterdir()]})
            rows.append({"stage_id": mid, "attempt": 1, "manifest_path": str(path),
                         "manifest_sha256": sha(path), "status": "passed"})
        rows += [{"stage_id": "07", "module_version": 7, "status": "planned"},
                 {"stage_id": "08", "status": "skipped"}, {"stage_id": "09", "status": "skipped"}]
        write(run / "run_manifest.json", {"stages": rows, "run_id": run.name, "writing_mode": "single",
              "draft_labels": ["A"], "shared_resource_bindings": resources,
              "config_snapshot": {"writing": {"architecture": architecture, "language_style": style},
                                  "analysis": {"method_library_resource": method_binding}}})
        headings = ["摘要", "一、问题的提出", "二、文献回顾", "三、理论分析与研究假设",
                    "四、研究设计", "五、实证结果", "六、结论与讨论", "参考文献"]
        entry, marker, intro = "作者，2020，《技术夹具》。", "作者（2020）", "技术夹具引用作者（2020）。"
        texts = ["技术夹具。\n\n关键词：甲；乙；丙；丁", intro, "夹具文献。", "夹具假设。",
                 "夹具设计。", "夹具系数0.125。", "夹具回答。", entry]
        md = "# 技术测试专用夹具\n\n" + "\n\n".join(f"## {head}\n\n{body}" for head, body in zip(headings, texts))
        (run / "A.md").write_text(md, encoding="utf-8")
        claims = [{"claim_id": str(i), "section": headings[i], "text": texts[i].split("\n")[0],
                   "claim_type": "result", "result_ids": [result]} for i in (0, 5, 6)]
        claims[1]["statistics"] = [{"result_id": result, "field": "estimate", "display": "0.125"}]
        claims.append({"claim_id": "source", "section": headings[1], "text": intro, "claim_type": "direct",
                       "evidence_ids": [evidence], "reference_ids": [paper]})
        checks = {row["check_id"]: {"status": "passed", "evidence_or_note": "技术测试专用"}
                  for row in read_checklist(stage07.CHECKLIST)}
        path = run / "draft_input.json"
        style_review = {head: {"text": body.split("\n")[0], "style_ids": ["ST01"], "application": "TEST句子对象"}
                        for head, body in zip(headings[:-1], texts[:-1])}
        write(path, {"drafts": {"A": {"manuscript": "A.md", "authorship": "技术夹具", "claims": claims,
                     "checks": checks, "language_review": style_review,
                     "references": [{"reference_id": paper, "marker": marker, "entry": entry}]}}})
        return path


if __name__ == "__main__":
    unittest.main()
