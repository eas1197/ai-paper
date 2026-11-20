"""技术夹具只验证工作流，不计入课题验收。"""
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "tools"))
import stage07
from manuscript07 import parse_structure, read_checklist, reported_value
from language07 import style_findings
from paragraph07 import prose_paragraphs
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
                prepared = stage07.prepare(p)
                task = load(prepared["writing_task"])
                self.assertEqual(prepared["paragraph_plan_status"], "outline_required")
                self.assertIn("R4", task["paragraph_outline"]["units"])
                outline_file = self.outline(request_path, p["pack_id"])
                with self.assertRaisesRegex(ValueError, "paragraph_plan_id"):
                    stage07.execute(p)
                output = StringIO()
                with redirect_stdout(output):
                    code = stage07.main(["prepare", "--run-id", run.name, "--paragraph-plan", str(outline_file)])
                self.assertEqual(code, 0, output.getvalue())
                prepared = json.loads(output.getvalue())
                compiled = load(prepared["paragraph_task"])
                result_task = next(r for r in compiled["paragraphs"] if r["section"] == "R")
                self.assertEqual([r["id"] for r in result_task["style_rules"]], ["ST03", "ST07", "ST13"])
                self.assertEqual(result_task["source_material"]["result_ids"][0]["estimate"], .125)
                self.assertEqual(result_task["next"]["paragraph_id"], "P7")
                self.assertEqual(stage07.prepare(p, outline_file)["paragraph_plan_id"], prepared["paragraph_plan_id"])
                with self.assertRaisesRegex(ValueError, "草稿标签"):
                    stage07.load_paragraph_plan(Path(prepared["frozen_manifest"]).parent, p["pack_id"], "B",
                                                prepared["paragraph_plan_id"], sha(prepared["writing_task"]))
                rules = task["writing_requirements"]
                self.assertEqual(rules["sha256"], sha(rules["path"]))
                self.assertIn("全文不写自我反驳", rules["text"])
                request = load(request_path)
                draft = request["drafts"]["A"]
                draft["pack_id"] = p["pack_id"]
                draft["paragraph_plan_id"] = prepared["paragraph_plan_id"]
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

    def test_prepare_uses_only_a_published_index_and_checks_its_hash(self):
        with tempfile.TemporaryDirectory(dir=MODULE / "tests") as folder:
            run = Path(folder).resolve()
            request_path = self.fixture(run)
            manifest = run / "run_manifest.json"
            data = load(manifest)
            binding = next(b for b in data["shared_resource_bindings"] if b["module_id"] == "03")
            snapshot = Path(binding["snapshot_manifest_path"])
            snapshot_data = load(snapshot)
            index = run / "writing_exemplars.json"
            subject = {"schema_version": 1, "status": "pilot",
                       "held_out_paper_ids": ["excluded"],
                       "papers": {"paper": {"design": "cross_section", "journal": "社会学研究", "title": "范例"}},
                       "examples": [{"example_id": "paper-question", "paper_id": "paper", "move": "question",
                                     "pdf_page": 1, "section": "引言", "source_anchor": "夹具",
                                     "before": "前文", "advance": "推进", "after": "下文",
                                     "style": "表达", "conditions": "适用条件", "topic": "家庭"}]}
            def publish_candidate():
                write(index, subject)
                snapshot_data["files"] = [r for r in snapshot_data["files"] if Path(r["path"]) != index]
                snapshot_data["files"].append(file_lock(index))
                write(snapshot, snapshot_data)
                binding["manifest_sha256"] = sha(snapshot)
                write(manifest, data)

            with patch.object(stage07, "run_directory", return_value=run):
                options = {"run_id": run.name}
                publish_candidate()
                self.assertEqual(stage07.plan(options)["status"], "needs_review")
                subject["examples"][0]["paper_id"] = "excluded"
                subject["status"] = "passed"
                publish_candidate()
                self.assertEqual(stage07.plan(options)["status"], "needs_review")
                subject["examples"][0]["paper_id"] = "paper"
                publish_candidate()
                plan = stage07.plan(options)
                self.assertEqual(plan["status"], "ready", plan["errors"])
                task = load(stage07.prepare(plan)["writing_task"])
                self.assertEqual(task["writing_exemplars"]["tasks"]["question"]["examples"][0]["example_id"],
                                 "paper-question")
                self.assertEqual(task["writing_exemplars"]["tasks"]["results"]["examples"], [])
                self.assertNotIn("source_anchor", task["writing_exemplars"]["tasks"]["question"]["examples"][0])
                outline = self.outline(request_path, plan["pack_id"])
                compiled = load(stage07.prepare(plan, outline)["paragraph_task"])
                self.assertEqual(compiled["paragraphs"][1]["examples"][0]["example_id"], "paper-question")
                index.write_text("改动", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "上游未就绪或已变化"):
                    stage07.prepare(plan)

    def test_paragraph_plan_rejects_wrong_rule_evidence_and_revision_mismatch(self):
        with tempfile.TemporaryDirectory(dir=MODULE / "tests") as folder:
            run = Path(folder).resolve()
            request_path = self.fixture(run)
            with patch.object(stage07, "run_directory", return_value=run):
                plan = stage07.plan({"run_id": run.name, "input": str(request_path)})
                outline_file = self.outline(request_path, plan["pack_id"])
                outline = load(outline_file)
                outline["paragraphs"][5]["sources"]["result_ids"] = ["wrong"]
                write(outline_file, outline)
                with self.assertRaisesRegex(ValueError, "未绑定冻结材料"):
                    stage07.prepare(plan, outline_file)
                outline_file = self.outline(request_path, plan["pack_id"])
                prepared = stage07.prepare(plan, outline_file)
                request = load(request_path)
                draft = request["drafts"]["A"]
                draft.update(pack_id=plan["pack_id"], paragraph_plan_id=prepared["paragraph_plan_id"])

                # An existing frozen citation may only be used in an assigned paragraph.
                outline = load(outline_file)
                outline["paragraphs"][1]["sources"] = {}
                write(outline_file, outline)
                alternate = stage07.prepare(plan, outline_file)
                self.assertNotEqual(alternate["paragraph_plan_id"], prepared["paragraph_plan_id"])
                draft["paragraph_plan_id"] = alternate["paragraph_plan_id"]
                draft["paragraph_review"]["P6"]["style_ids"] = ["ST14"]
                write(request_path, request)
                response = stage07.execute(plan)
                self.assertEqual(response["status"], "needs_review")
                self.assertTrue(any("P2" in e and "未分配到本段" in e for e in response["errors"]))
                self.assertTrue(any("P6" in e and "风格规则" in e for e in response["errors"]))

                manuscript = run / draft["manuscript"]
                with manuscript.open("r", encoding="utf-8") as stream:
                    text = stream.read()
                manuscript.write_text(text.replace("夹具系数0.125。", "夹具系数0.125。\n\n新增测试段。"),
                                      encoding="utf-8")
                response = stage07.execute(plan)
                self.assertTrue(any("合并或拆分" in e for e in response["errors"]))

                compiled_path = Path(alternate["paragraph_task"])
                write(compiled_path, dict(load(compiled_path), edited=True))
                with self.assertRaisesRegex(ValueError, "段落任务的内容"):
                    stage07.execute(plan)

    def outline(self, request_path, pack_id):
        manuscript = request_path.parent / "A.md"
        blocks = list(prose_paragraphs(manuscript.read_text(encoding="utf-8")))
        units = (["S1", "S4"], ["I3"], ["L0"], ["T0"], ["D1"], ["R4"], ["C1"])
        paragraphs = []
        for i, ((heading, _), codes) in enumerate(zip(blocks, units), 1):
            sources = {}
            if i in (1, 6, 7):
                sources["result_ids"] = ["fixture-result"]
            if i == 2:
                sources["evidence_ids"] = ["fixture-evidence"]
            paragraphs.append({"paragraph_id": f"P{i}", "heading": heading, "units": codes,
                               "continues": "技术夹具承接", "purpose": "技术夹具验证", "sources": sources})
        path = request_path.parent / "outline.json"
        write(path, {"schema_version": 1, "pack_id": pack_id, "label": "A", "paragraphs": paragraphs})
        return path

    def fixture(self, run):
        architecture = load(MODULE / "manifest.json")["writing_architecture"]
        profile = ROOT / "03_学术语言学习/v005_第5版/outputs/style_profile.json"
        style_binding = file_lock(profile)
        style = {"profile_path": style_binding["path"], "profile_sha256": style_binding["sha256"]}
        style_profile = load(profile)
        resources = []
        for mid, files in (("02", [architecture["profile_path"], architecture["guide_path"]]),
                           ("03", [style["profile_path"], *(row["path"] for row in style_profile["paragraph_style"].values())])):
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
        rows += [{"stage_id": "07", "module_version": stage07.VERSION, "status": "planned"},
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
        style_review = {f"P{i}": {"text": body.split("\n")[0], "style_ids": [rule], "application": "技术夹具表达定位"}
                        for i, (body, rule) in enumerate(zip(texts, (
                            "ST01", "ST01", "ST01", "ST02", "ST01", "ST03", "ST01")), 1)}
        write(path, {"drafts": {"A": {"manuscript": "A.md", "authorship": "技术夹具", "claims": claims,
                     "checks": checks, "paragraph_review": style_review,
                     "references": [{"reference_id": paper, "marker": marker, "entry": entry}]}}})
        return path


if __name__ == "__main__":
    unittest.main()
