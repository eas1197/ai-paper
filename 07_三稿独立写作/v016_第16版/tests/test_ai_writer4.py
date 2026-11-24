"""Offline contract tests for ai-writer 4.0 qualitative drafting bridge."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ai_writer4 as writer


def packet(method="secondary_interviews"):
    dimensions = [{"id": "d1", "title": "可信性", "deduction": "derive uncertainty management"}]
    chapter_ids = ["problem", "framework", "case", "d1", "conclusion"]
    chapters = []
    for cid in chapter_ids:
        chapters.append({
            "id": cid, "task": "Explain this specific relation",
            "bridge": "Continue from earlier evidence",
            "sections": [{
                "title": "Study", "task": "Compare two situations",
                "argument": "Claims bounded to reported action",
                "evidence_use": "Use cited material to distinguish facts from claims",
                "source_ids": ["E", "T"],
                "paragraphs": ["State the unit and observed action"]
            }]
        })
    return {
        "run_id": "fixture_writer4", "method": method,
        "core_question": "How does coordination proceed?",
        "answer_strategy": "Compare reported sequences",
        "framework": {
            "prior_explanation": "Prior studies", "gap": "Comparable boundaries",
            "theory_choice": "Action organization", "deduction": "Define testable dimensions",
            "increment": "Provisional comparison", "integration": "Connect dimensions",
            "core_concept": "行动可执行性", "dimensions": dimensions
        },
        "case": {
            "background": "Two cases", "selection": "Relevant variation",
            "materials": "Two linked reports", "method": "Comparative document analysis"
        },
        "sources": {
            "T": {"kind": "theory", "label": "Literature", "locator": "DOI 123"},
            "E": {"kind": "empirical", "label": "Interview report", "locator": "URL line 22"}
        },
        "chapters": chapters,
        "gate_status": {
            "independent_review_verified": False,
            "strict_literature_complete": False,
            "empirical_mechanism_verified": False,
            "formally_frozen": False,
            "independent_writing_approval": False,
        },
        "policy": {"max_words": 2500}
    }


class Writer4Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = packet()
        self.packet_path = self.root / "input.json"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.work = self.root / "writing"

    def tearDown(self):
        self.tmp.cleanup()

    def test_qualitative_preparation_reuses_exact_language_resources(self):
        record = writer.prepare(self.packet_path, self.work)
        self.assertEqual(record["task_count"], 5)
        self.assertEqual(record["status"], "awaiting_draft")
        manifest = writer.load(self.work / "writer_manifest.json")
        self.assertEqual(manifest["language_formal_resource_status"], "needs_review")
        self.assertFalse(manifest["formal_eligible"])
        self.assertEqual(len(manifest["resource_sha256"]), 13)
        self.assertEqual(manifest["language_resource_version"], 3)
        self.assertEqual(manifest["language_snapshot_id"], "language_style_r3_paragraph_units_candidate")
        self.assertEqual(manifest["v003_resource_version"], 1)
        self.assertEqual(manifest["v004_resource_version"], 2)
        self.assertIn("03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/language_evidence.jsonl",
                      {item["path"] for item in manifest["resource_snapshot_warnings"]})
        task = writer.load(self.work / "tasks/d1_01.json")
        self.assertIn("how_to_write", task["style_rules"][0])
        self.assertTrue(task["v005_unit_details_as_style_hints_only"][0]["purpose"])
        self.assertTrue(task["v003_argument_rules"][0]["principle"])
        self.assertTrue(task["v003_argument_rules"][0]["syntax_and_information_order"])
        self.assertTrue(task["v003_argument_rules"][0]["usage_condition"])
        self.assertTrue(task["v003_argument_rules"][0]["project_constraint"])
        self.assertEqual(task["language_resource_versions"], {"v003": 1, "v004": 2, "v005": 3})
        self.assertEqual(manifest["v003_argument_rule_count"], 27)
        self.assertEqual(manifest["v005_function_unit_count"], 52)
        rolemap = writer.language_resources()[2]["chapters"]
        for chapter in self.data["chapters"]:
            expected = rolemap[writer.stage_type(chapter["id"])]
            chapter_task = writer.load(self.work / "tasks" / (chapter["id"] + "_01.json"))
            self.assertEqual(chapter_task["style_rule_ids"], expected["style_ids"])
            self.assertEqual([x["id"] for x in chapter_task["v005_unit_details_as_style_hints_only"]],
                             expected["v005_units"])
            self.assertEqual([x["id"] for x in chapter_task["v003_argument_rules"]],
                             expected["argument_audit"])
        self.assertIn("分析框架", (self.work / "writing_plan_v15.md").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "exists"):
            writer.prepare(self.packet_path, self.work)

    def test_language_snapshots_bind_versions_status_and_all_files(self):
        profile, snapshot, rolemap, rules, units, locks, argument_rules, warnings, versions = writer.language_resources()
        self.assertEqual(profile["profile_version"], "3.0")
        self.assertEqual(profile["resource_version"], 3)
        self.assertEqual(versions, {"v003": 1, "v004": 2, "v005": 3})
        self.assertEqual(profile["formal_resource_gate_status"], "needs_review")
        self.assertEqual(snapshot["status"], "needs_review")
        self.assertFalse(snapshot["resource_available_for_formal_writing"])
        self.assertIn("v003_resource_snapshot", locks)
        self.assertIn("v004_style_profile", locks)
        self.assertIn("v004_resource_snapshot", locks)
        warning_paths = {item["path"] for item in warnings}
        self.assertIn("03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/language_evidence.jsonl", warning_paths)
        self.assertEqual(len(argument_rules), 27)
        self.assertTrue(all(rule["principle"] and rule["project_constraint"]
                            for rule in argument_rules.values()))
        self.assertEqual(len(units), 52)

    def test_unreferenced_snapshot_file_hash_change_is_recorded(self):
        original_hash = writer.hash_file
        target = writer.ROOT / "03_学术语言学习/v004_第4版/outputs/language_audit.csv"
        def altered_hash(path):
            if Path(path).resolve() == target.resolve():
                return "0" * 64
            return original_hash(path)
        with patch.object(writer, "hash_file", side_effect=altered_hash):
            profile, snapshot, rolemap, rules, units, locks, argument_rules, warnings, versions = writer.language_resources()
        self.assertIn("03_学术语言学习/v004_第4版/outputs/language_audit.csv",
                      {item["path"] for item in warnings})

    def test_active_language_handbook_hash_mismatch_is_rejected(self):
        original_hash = writer.hash_file
        target = writer.LANGUAGE_V3.resolve()
        def altered_hash(path):
            if Path(path).resolve() == target:
                return "0" * 64
            return original_hash(path)
        with patch.object(writer, "hash_file", side_effect=altered_hash):
            with self.assertRaisesRegex(ValueError, "dependency changed: v003"):
                writer.language_resources()

    def test_needs_review_resource_blocks_formal_mode_even_with_upstream_flags(self):
        self.data["gate_status"] = {key: True for key in writer.STATUSES}
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Formal G3 language resource has not passed business review"):
            writer.prepare(self.packet_path, self.work, mode="formal")
        self.assertFalse(self.work.exists())

    def test_routes_quantitative_to_existing_v014_without_change(self):
        self.data["method"] = "quantitative"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.assertIn("v014", writer.route(self.packet_path)["writer"])
        with self.assertRaisesRegex(ValueError, "v014"):
            writer.prepare(self.packet_path, self.work)

    def test_formal_drafting_does_not_invent_independent_receipt(self):
        with self.assertRaisesRegex(ValueError, "upstream gates"):
            writer.prepare(self.packet_path, self.work, mode="formal")
        self.assertFalse(self.work.exists())

    def test_audits_source_bound_claims_and_rejects_changed_input(self):
        writer.prepare(self.packet_path, self.work)
        draft = self.root / "draft.md"
        draft.write_text(
            "## 一、问题\n材料表明需要协调（来源，2022）。\n"
            "## 二、理论\n对照理论与报道。\n"
            "## 三、案例\n案例为两个组织。\n"
            "## 四、可信性\n报道中的核验行为。\n"
            "## 五、结论\n材料表明需要协调。\n"
            "## 参考文献\n来源（2022）。\n", encoding="utf-8")
        claims = self.root / "claims.json"
        claims.write_text(json.dumps({"claims": [{"claim_id": "C1",
            "exact_text": "材料表明需要协调", "source_ids": ["E", "T"]}]}, ensure_ascii=False), encoding="utf-8")
        output = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertEqual(output["status"], "exploratory_draft_awaiting_review")
        self.assertFalse(writer.load(self.work / "writing_review_request.json")["formal_pass"])
        self.data["core_question"] = "Different question?"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        result = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertEqual(result["status"], "technical_revisions_needed")
        self.assertTrue(any("packet changed" in s for s in result["errors"]))

    def test_style_review_is_diagnostic_only_and_preserves_evidence(self):
        writer.prepare(self.packet_path, self.work)
        draft = self.root / "draft.md"
        draft.write_text(
            "## 一、问题\n这一结果表明相关而非因果（来源，2022）。\n"
            "## 二、理论\n对照理论与报道。\n"
            "## 三、案例\n受访者原话为“尚不确定”。\n"
            "## 四、可信性\n报道中的核验行为。\n"
            "## 五、结论\n仅支持相关关系。\n",
            encoding="utf-8")
        claims = self.root / "claims.json"
        writer.save(claims, {"claims": [{"claim_id": "C1",
            "exact_text": "相关而非因果", "source_ids": ["E"]}]})
        before = (draft.read_bytes(), claims.read_bytes())
        output = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertGreater(output["style_issue_count"], 0)
        self.assertEqual(before, (draft.read_bytes(), claims.read_bytes()))
        review = writer.load(self.work / "style_review.json")
        self.assertEqual(review["edit_policy"], "diagnostic_only")
        self.assertEqual(review["semantic_equivalence"], "not_verified")
        self.assertEqual(review["manuscript_sha256"], writer.hash_file(draft))
        self.assertEqual(review["claim_ledger_sha256"], writer.hash_file(claims))
        self.assertTrue({"research_conclusion", "source_attribution",
                         "interview_and_quote_authenticity", "causal_strength"}
                        <= set(review["protected_boundaries"]))
        self.assertFalse(writer.load(self.work / "writing_review_request.json")["formal_pass"])

    def test_language_resource_failure_stops_submit_and_invalidates_candidate(self):
        writer.prepare(self.packet_path, self.work)
        draft = self.root / "draft.md"
        draft.write_text("## 一\n材料。\n", encoding="utf-8")
        claims = self.root / "claims.json"
        writer.save(claims, {"claims": []})
        writer.save(self.work / "writing_review_request.json",
                    {"status": "exploratory_draft_awaiting_review", "formal_pass": False})
        before = (draft.read_bytes(), claims.read_bytes())
        for failure in (FileNotFoundError("missing language resource"),
                        ValueError("Language snapshot dependency changed"),
                        ValueError("Invalid qualitative map or v005/V003 rule reference")):
            with patch.object(writer, "language_resources", side_effect=failure):
                result = writer.review_draft(self.packet_path, self.work, draft, claims)
            self.assertEqual(result["language_resource_status"], "pending_recheck")
            self.assertEqual(result["status"], "technical_revisions_needed")
            saved = writer.load(self.work / "writing_review_request.json")
            self.assertFalse(saved["formal_pass"])
            self.assertEqual(saved["language_resource_status"], "pending_recheck")
            self.assertFalse((self.work / "style_review.json").exists())
            self.assertEqual(before, (draft.read_bytes(), claims.read_bytes()))

    def test_language_lock_change_stops_before_new_style_review(self):
        writer.prepare(self.packet_path, self.work)
        draft = self.root / "draft.md"
        draft.write_text("材料。", encoding="utf-8")
        claims = self.root / "claims.json"
        writer.save(claims, {"claims": []})
        resources = list(writer.language_resources())
        resources[5] = dict(resources[5], changed={"sha256": "0" * 64})
        with patch.object(writer, "language_resources", return_value=tuple(resources)):
            result = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertEqual(result["language_resource_status"], "pending_recheck")
        self.assertFalse((self.work / "style_review.json").exists())

    def test_rejects_missing_evidence_from_dimension(self):
        self.data["chapters"][3]["sections"][0]["source_ids"] = ["T"]
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "empirical"):
            writer.prepare(self.packet_path, self.work)


    def test_existing_digital_mutual_aid_package_connects_without_formal_pass(self):
        """Actual archived V15 input and source-bound A specimen, not invented fixture evidence."""
        base = (writer.ROOT / "handoff_runs/digital_mutual_aid_20261122"
                / "chat_native_20261122/writing")
        old_input = base / "写作任务V15输入.json"
        old_manuscript = base / "A稿_探索性正文.md"
        old_claims = base / "主张证据台账.json"
        for item in (old_input, old_manuscript, old_claims):
            self.assertTrue(item.is_file(), str(item))
        self.assertIn("v016", writer.route(old_input)["writer"])
        response = writer.prepare(old_input, self.work)
        self.assertEqual(response["task_count"], 14)
        self.assertEqual(response["language_gate"], "needs_review")
        report = writer.review_draft(old_input, self.work, old_manuscript, old_claims)
        self.assertEqual(report["status"], "exploratory_draft_awaiting_review")
        self.assertEqual(writer.load(self.work / "writing_review_request.json")["independent_review"], "pending")


    def test_dev_controller_dispatch_is_opt_in_and_qualitative_only(self):
        sys.path.insert(0, str(writer.ROOT / "00_项目控制/v007_第7版/tools"))
        import run_mode
        with patch.object(run_mode, "RUNS", self.root):
            run_mode.start("writer4_dispatch_fixture", "Digital mutual aid")
            argv = ["run_mode.py", "--mode", "dev", "--run-id", "writer4_dispatch_fixture",
                    "--writer4", "route", "--packet", str(self.packet_path)]
            with patch.object(sys, "argv", argv), patch.object(run_mode.subprocess, "call", return_value=0) as mocked:
                self.assertEqual(run_mode.main(), 0)
                args = mocked.call_args.args[0]
                self.assertIn("ai_writer4.py", args[2])
                self.assertEqual(args[3:], ["route", "--packet", str(self.packet_path)])


if __name__ == "__main__":
    unittest.main()
